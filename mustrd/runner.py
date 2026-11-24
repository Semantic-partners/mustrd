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
from dataclasses import dataclass, field
from pathlib import Path

from rdflib import Graph, URIRef

from mustrd.mustrd import (
    validate_specs, get_specs, run_spec, review_results,
    SpecPassed, SpecPassedWithWarning,
    get_triple_store_graph, get_triple_stores, get_credentials,
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
                get_triple_store_graph(test_config.triplestore_spec_path),
                get_credentials(test_config.triplestore_spec_path, secrets),
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


def triple_store_name(spec):
    ts = getattr(spec, "triple_store", None)
    if isinstance(ts, dict):
        return str(ts.get("uri") or ts.get("type") or "rdflib").split("/")[-1].split("#")[-1]
    return str(ts).split("/")[-1].split("#")[-1] if ts else "rdflib"


def _config_files(config_paths):
    # One config file or several; a single path is still accepted.
    if isinstance(config_paths, (str, os.PathLike)):
        config_paths = [config_paths]
    return [Path(p) for p in config_paths]


def static_triple_stores(test_config):
    """The stores a TestConfig is measured against when nothing runs.

    Static coverage never contacts a store, so it reads no connection config and
    no credentials: not triplestoreSpecPath, not a `_secrets` file, not
    `:tokenEnv` / `:tokenFile`. One placeholder per `filterOnTripleStore` value,
    typed rdflib so nothing treats it as a live server, and named after the
    filter so test names still read `spec@CiscStardog`. With no filter, the
    rdflib store. Never empty, so a suite can never resolve to no store and lose
    its specs silently.
    """
    if test_config.filter_on_tripleStore:
        return [{"type": TRIPLESTORE.RdfLib, "uri": URIRef(str(f))}
                for f in test_config.filter_on_tripleStore]
    return [dict(_RDFLIB_STORE)]


def _built_specs(config_paths, stores_for, selected_tests=None, ignore_focus=False):
    """Build (but do not run) every spec in the configs, against the stores
    `stores_for(test_config)` returns. Returns a (test_config, specs, skipped)
    triple per TestConfig, and the hasSpecPath dirs."""
    test_configs = [tc for f in _config_files(config_paths) for tc in parse_config(f)]
    per_config = []
    for test_config in test_configs:
        triple_stores = stores_for(test_config)
        # validate_specs / get_specs expect a run_config dict, not the TestConfig
        # dataclass — the same shape the plugin builds during collection.
        run_cfg = {"spec_path": test_config.spec_path,
                   "data_path": test_config.data_path}
        specs, skipped = generate_specs(run_cfg, triple_stores,
                                        selected_tests=selected_tests,
                                        ignore_focus=ignore_focus)
        per_config.append((test_config, specs, skipped))
    return per_config, [tc.spec_path for tc in test_configs if tc.spec_path]


@dataclass
class StaticSpecs:
    """What static collection found: the coverage inputs, and every spec left
    out with the reason.

    `left_out` is a list of {"name", "reason"}: specs that failed validation or
    could not be built (e.g. an Anzo-only source with no Anzo to read from).
    """
    all_specs: list = field(default_factory=list)
    spec_by_uri: dict = field(default_factory=dict)
    spec_paths: list = field(default_factory=list)
    left_out: list = field(default_factory=list)

    def summary(self):
        # Distinct specs, not spec×store: a suite filtered to two stores builds
        # each spec twice, and the count is of specs.
        n = len({s.get("uri") or s.get("test_name") for s in self.all_specs})
        m = len(self.left_out)
        return f"{n} spec{'' if n == 1 else 's'} measured, {m} not counted"


def collect_static(config_paths, selected_tests=None, ignore_focus=False) -> StaticSpecs:
    """Build every spec in the configs and run none, against placeholder stores
    (see `static_triple_stores`): no network, no credentials.

    Every spec that builds is credited as passing: coverage then reads what the
    specs say (their given data and queries), not whether they hold against a
    store. Specs that fail validation or cannot be built go in `left_out`.
    """
    per_config, spec_paths = _built_specs(config_paths, static_triple_stores,
                                          selected_tests, ignore_focus)
    out = StaticSpecs(spec_paths=spec_paths)
    for _tc, specs, skipped in per_config:
        for spec in specs:
            test_name = f"{getattr(spec, 'spec_file_name', spec.spec_uri)}@{triple_store_name(spec)}"
            cspec = coverage_spec(spec, "passed", test_name)
            cspec["test_name"] = test_name
            out.all_specs.append(cspec)
            if cspec.get("uri"):
                out.spec_by_uri[cspec["uri"]] = cspec
        # One entry per spec, not per store: an invalid spec is recorded once for
        # each store it was tried on, and carries only the store's type.
        seen = set()
        for sk in skipped:
            uri = getattr(sk, "spec_uri", None)
            name = getattr(sk, "spec_file_name", None) or (str(uri) if uri else "unknown")
            reason = (getattr(sk, "message", None) or type(sk).__name__).strip()
            reason = reason.splitlines()[0] if reason else ""
            if (str(uri), name) in seen:
                continue
            seen.add((str(uri), name))
            out.left_out.append({"name": name, "reason": reason})
    return out


def collect_specs(config_paths, secrets=None, selected_tests=None, ignore_focus=False):
    """The coverage inputs for the configs' specs WITHOUT running any of them.

      (all_specs, spec_by_uri, spec_paths)

    See `collect_static`, which also reports the specs left out. `secrets` is
    accepted for compatibility and ignored: nothing here connects to a store.
    """
    found = collect_static(config_paths, selected_tests, ignore_focus)
    return found.all_specs, found.spec_by_uri, found.spec_paths


def static_coverage(config_paths, opts=None, secrets=None, selected_tests=None,
                    ignore_focus=False, terminal_writer=None, collected=None):
    """Term coverage for one or more MustrdTest configs, WITHOUT running the tests.

    Builds the specs, credits each one as passing (see `collect_static`), and
    writes whatever `opts` (a `mustrd.reporting.ReportOptions`) asks for: --md,
    the coverage graph, the viewer. With no `opts`, computes term coverage and the
    competency-question overlay and writes nothing. Ontology paths default to the
    configs' hasOntologyPath.

    No store is contacted and no credentials are read. `secrets` is accepted for
    compatibility and ignored. Pass `collected` (from `collect_static`) to reuse
    a collection, e.g. to report its counts; specs left out are logged as a
    warning either way.

    Returns `coverage`, the template context dict (`covered`, `queried`, `pct`,
    `queried_pct`, ...), or None when no ontology terms are declared.
    """
    from mustrd.reporting import (ReportOptions, collect_cq_defs, produce_report,
                                  wants_cq)
    opts = opts or ReportOptions(term_coverage=True, cq=True)
    if not opts.ontology_paths:
        opts.ontology_paths = tuple(ontology_paths_from_config(config_paths))
    found = collected or collect_static(config_paths, selected_tests, ignore_focus)
    for lo in found.left_out:
        logger.warning(f"not counted in coverage: {lo['name']}: {lo['reason']}")
    cq_defs = collect_cq_defs(found.spec_paths, found.spec_by_uri) if wants_cq(opts) else []
    coverage, _ontology_graph, _graph = produce_report(
        found.all_specs, cq_defs, [], True, opts, terminal_writer=terminal_writer)
    return coverage


def run_config(config_paths, secrets=None, selected_tests=None, ignore_focus=False,
               verbose=False, review=False):
    """Run every spec in one or more MustrdTest config files and return the plain-data inputs the
    reporting library consumes:

      (results, all_specs, spec_by_uri, test_results, run_results, spec_paths)

    - results: the SpecResults (passed/failed + skipped/invalid), for review.
    - all_specs / spec_by_uri: coverage spec-dicts (as the plugin builds them).
    - test_results: a TestResult per run spec, for the plain --md ResultList.
    - run_results: a RunResult per test (incl. skipped/invalid), for the results graph.
    - spec_paths: hasSpecPath dirs, for competency-question discovery.
    """
    results, all_specs, spec_by_uri, test_results, run_results = [], [], {}, [], []
    per_config, spec_paths = _built_specs(
        config_paths, lambda tc: resolve_triple_stores(tc, secrets),
        selected_tests, ignore_focus)

    for _tc, specs, skipped in per_config:
        for spec in specs:
            ts = triple_store_name(spec)
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


def ontology_paths_from_config(config_paths):
    """All hasOntologyPath values across the configs' TestConfigs (for coverage)."""
    return [p for f in _config_files(config_paths)
            for tc in parse_config(f) for p in tc.ontology_paths]
