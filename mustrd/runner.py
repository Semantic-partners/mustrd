"""Run mustrd specs without pytest — the orchestration the `mustrd` CLI needs.

Mirrors what the pytest plugin does at collection + run time, reusing the same
mustrd.py pipeline (validate_specs -> get_specs -> run_spec) and the same
`mustrd.config` TestConfig, so the CLI and the plugin execute identical specs.
The pytest plugin delegates its spec-generation to the functions here, keeping a
single source of truth.
"""
import logging
import os
import time
from pathlib import Path

from rdflib import Graph

from mustrd.mustrd import (
    validate_specs, get_specs, run_spec, review_results,
    SpecPassed, SpecPassedWithWarning,
    get_triple_store_graph, get_triple_stores,
)
from mustrd.config import parse_config
from mustrd.namespace import TRIPLESTORE
from mustrd.reporting import coverage_spec
from mustrd.results_rdf import RunResult
from mustrd.TestResult import TestResult
from mustrd.utils import get_mustrd_root

logger = logging.getLogger(__name__)
mustrd_root = get_mustrd_root()

_RDFLIB_STORE = {"type": TRIPLESTORE.RdfLib, "uri": TRIPLESTORE.RdfLib}


def resolve_triple_stores(test_config, secrets=None):
    """The triple stores a TestConfig runs against — from its
    triplestoreSpecPath, or embedded rdflib, then filtered by
    filterOnTripleStore. (Extracted from the plugin's
    get_triple_stores_from_file so the CLI shares it.)"""
    if test_config.triplestore_spec_path:
        try:
            triple_stores = get_triple_stores(
                get_triple_store_graph(test_config.triplestore_spec_path, secrets)
            )
        except Exception as e:
            print(
                f"""Triplestore configuration parsing failed {test_config.triplestore_spec_path}.
                Only rdflib will be executed""",
                e,
            )
            triple_stores = [dict(_RDFLIB_STORE)]
    else:
        logger.debug("No triple store configuration required: using embedded rdflib")
        triple_stores = [dict(_RDFLIB_STORE)]

    if test_config.filter_on_tripleStore:
        triple_stores = list(
            filter(
                lambda triple_store: (
                    triple_store["uri"] in test_config.filter_on_tripleStore
                ),
                triple_stores,
            )
        )
    return triple_stores


def generate_specs(config, triple_stores, file_name="*", selected_tests=None,
                   ignore_focus=False):
    """Validate + build the Specifications for one TestConfig across the given
    triple stores. Returns runnable specs + skipped/invalid SpecResults.
    (Extracted from the plugin's generate_tests_for_config.)"""
    shacl_graph = Graph().parse(Path(os.path.join(mustrd_root, "model/mustrdShapes.ttl")))
    ont_graph = Graph().parse(Path(os.path.join(mustrd_root, "model/ontology.ttl")))

    valid_spec_uris, spec_graph, invalid_specs = validate_specs(
        config, triple_stores, shacl_graph, ont_graph, file_name or "*",
        selected_test_files=selected_tests or [], ignore_focus=ignore_focus,
    )
    specs, skipped_spec_results = get_specs(
        valid_spec_uris, spec_graph, triple_stores, config
    )
    return specs, skipped_spec_results + invalid_specs


def _outcome(result):
    """'passed' / 'failed' for a SpecResult (mirrors the plugin's pytest
    outcome for coverage purposes)."""
    return "passed" if isinstance(result, (SpecPassed, SpecPassedWithWarning)) else "failed"


def _triple_store_name(spec):
    ts = getattr(spec, "triple_store", None)
    if isinstance(ts, dict):
        return str(ts.get("uri") or ts.get("type") or "rdflib").split("/")[-1].split("#")[-1]
    return str(ts).split("/")[-1].split("#")[-1] if ts else "rdflib"


def run_config(config_path, secrets=None, selected_tests=None, ignore_focus=False,
               verbose=False, review=False):
    """Run every spec in a MustrdTest config and return the plain-data inputs the
    reporting library consumes:

      (results, all_specs, spec_by_uri, test_results, run_results, spec_paths)

    - results: the SpecResults (passed/failed + skipped/invalid), for review.
    - all_specs / spec_by_uri: coverage spec-dicts (as the plugin builds them).
    - test_results: a TestResult per run spec, for the plain --md ResultList.
    - run_results: a RunResult per test (incl. skipped/invalid), for the results graph.
    - spec_paths: hasSpecPath dirs, for competency-question discovery.
    """
    test_configs = parse_config(Path(config_path))
    results, all_specs, spec_by_uri, test_results, run_results = [], [], {}, [], []
    spec_paths = [tc.spec_path for tc in test_configs if tc.spec_path]

    for test_config in test_configs:
        triple_stores = resolve_triple_stores(test_config, secrets)
        # validate_specs / get_specs expect a run_config dict, not the TestConfig
        # dataclass — the same shape the plugin builds during collection.
        run_cfg = {"spec_path": test_config.spec_path,
                   "data_path": test_config.data_path}
        specs, skipped = generate_specs(run_cfg, triple_stores,
                                        selected_tests=selected_tests,
                                        ignore_focus=ignore_focus)
        for spec in specs:
            ts = _triple_store_name(spec)
            t0 = time.perf_counter()
            result = run_spec(spec)
            duration = time.perf_counter() - t0
            results.append(result)
            outcome = _outcome(result)
            test_name = f"{getattr(spec, 'spec_file_name', spec.spec_uri)}@{ts}"
            test_results.append(TestResult(test_name, ts, "mustrd", outcome, True))
            uri = getattr(spec, "spec_uri", None)
            src = getattr(spec, "spec_source_file", None)
            run_results.append(RunResult(
                status=outcome, test_type="mustrd", module="mustrd",
                class_name=ts, test_name=test_name,
                spec_uri=str(uri) if uri is not None else None,
                spec_file_name=getattr(spec, "spec_file_name", None),
                source_file=str(src) if src is not None else None,
                duration=duration))
            cspec = coverage_spec(spec, outcome, test_name)
            all_specs.append(cspec)
            if cspec.get("uri"):
                spec_by_uri[cspec["uri"]] = cspec
        # Skipped/invalid specs still count as results for review, and appear as
        # skipped in the results graph.
        results.extend(skipped)
        for sk in skipped:
            uri = getattr(sk, "spec_uri", None)
            ts = str(getattr(sk, "triple_store", "")).split("/")[-1].split("#")[-1]
            src = getattr(sk, "spec_source_file", None)
            name = getattr(sk, "spec_file_name", None) or (str(uri) if uri else "unknown")
            run_results.append(RunResult(
                status="skipped", test_type="mustrd", module="mustrd",
                class_name=ts, test_name=f"{name}@{ts}",
                spec_uri=str(uri) if uri is not None else None,
                spec_file_name=getattr(sk, "spec_file_name", None),
                source_file=str(src) if src is not None else None))

    if review:
        review_results(results, verbose)
    return results, all_specs, spec_by_uri, test_results, run_results, spec_paths


def ontology_paths_from_config(config_path):
    """All hasOntologyPath values across a config's TestConfigs (for coverage)."""
    return [p for tc in parse_config(Path(config_path)) for p in tc.ontology_paths]
