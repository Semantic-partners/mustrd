import logging
from dataclasses import dataclass
import pytest
import os
from pathlib import Path
from rdflib.namespace import Namespace
from rdflib import Graph, RDF
from pytest import Session

from mustrd import logger_setup
from mustrd.TestResult import (
    TestResult, render_cq_table, render_term_coverage, render_ontologies,
    render_duplicate_cqs, render_per_cq, render_cq_gaps, render_tbox_in_data,
    ResultList, get_result_list,
)
from mustrd.coverage import compute_coverage
from mustrd.ontology import load_ontology, ontology_report
from mustrd.cq import cq_facts
from mustrd.coverage_rdf import coverage_graph, cq_graph
from mustrd.coverage_render import coverage_context, read_ontologies
from mustrd.cq_render import cq_report
from mustrd.utils import get_mustrd_root
from mustrd.mustrd import (
    validate_specs,
    get_specs,
    SpecPassed,
    run_spec,
    write_result_diff_to_log,
    get_triple_store_graph,
    get_triple_stores,
    SpecInvalid
)
from mustrd.namespace import MUST, TRIPLESTORE, MUSTRDTEST, CQ
from pyshacl import validate

import pathlib
import traceback

spnamespace = Namespace("https://semanticpartners.com/data/test/")

mustrd_root = get_mustrd_root()

MUSTRD_PYTEST_PATH = "mustrd_tests/"


def pytest_addoption(parser):
    group = parser.getgroup("mustrd option")
    group.addoption(
        "--mustrd",
        action="store_true",
        dest="mustrd",
        help="Activate/deactivate mustrd test generation.",
    )
    group.addoption(
        "--md",
        action="store",
        dest="mdpath",
        metavar="pathToMdSummary",
        default=None,
        help="create md summary file at that path.",
    )
    group.addoption(
        "--config",
        action="store",
        dest="configpath",
        metavar="pathToTestConfig",
        default=None,
        help="Ttl file containing the list of test to construct.",
    )
    group.addoption(
        "--secrets",
        action="store",
        dest="secrets",
        metavar="Secrets",
        default=None,
        help="Give the secrets by command line in order to be able to store secrets safely in CI tools",
    )
    group.addoption(
        "--pytest-path",
        action="store",
        dest="pytest_path",
        metavar="PytestPath",
        default=None,
        help="Filter tests based on the pytest_path property in .mustrd.ttl files.",
    )
    group.addoption(
        "--ignore-focus",
        action="store_true",
        dest="ignore_focus",
        help="Activate/deactivate focus: if --ignore-focus is set, focus will be ignored.",
    )
    group.addoption(
        "--term-coverage",
        action="store_true",
        dest="term_coverage",
        help="Report ontology term coverage across ALL mustrd tests: which "
             "declared terms the passing tests exercise (in data or SPARQL). "
             "Prints a percentage and table to stdout; also written to --md.",
    )
    group.addoption(
        "--cq",
        action="store_true",
        dest="cq",
        help="Add competency-question sections to the report: a Competency "
             "Questions table and a per-CQ breakdown. Combined with "
             "--term-coverage it also shows how much of the ontology the CQs "
             "(vs all tests) cover.",
    )
    group.addoption(
        "--term-coverage-rdf",
        action="store",
        dest="term_coverage_rdf",
        metavar="pathToRdf",
        default=None,
        help="Write ontology term coverage as RDF (Turtle, W3C DQV + PROV) to "
             "this path — DQV quality measurements computedOn the ontology, a "
             "per-term breakdown, and quality issues, for a knowledge graph. "
             "Needs an ontology (:hasOntologyPath).",
    )
    return


def pytest_configure(config) -> None:
    # Read configuration file
    if config.getoption("mustrd") and config.getoption("configpath"):
        config.pluginmanager.register(
            MustrdTestPlugin(
                config.getoption("mdpath"),
                Path(config.getoption("configpath")),
                config.getoption("secrets"),
                config.getoption("ignore_focus"),
                config.getoption("term_coverage"),
                config.getoption("cq"),
                config.getoption("term_coverage_rdf"),
            )
        )


def parse_config(config_path):
    test_configs = []
    config_graph = Graph().parse(config_path)
    shacl_graph = Graph().parse(
        Path(os.path.join(mustrd_root, "model/mustrdTestShapes.ttl"))
    )
    ont_graph = Graph().parse(
        Path(os.path.join(mustrd_root, "model/mustrdTestOntology.ttl"))
    )
    conforms, results_graph, results_text = validate(
        data_graph=config_graph,
        shacl_graph=shacl_graph,
        ont_graph=ont_graph,
        advanced=True,
        inference="none",
    )
    if not conforms:
        raise ValueError(
            f"Mustrd test configuration not conform to the shapes. SHACL report: {results_text}",
            results_graph,
        )

    for test_config_subject in config_graph.subjects(
        predicate=RDF.type, object=MUSTRDTEST.MustrdTest
    ):
        spec_path = get_config_param(
            config_graph, test_config_subject, MUSTRDTEST.hasSpecPath, str
        )
        data_path = get_config_param(
            config_graph, test_config_subject, MUSTRDTEST.hasDataPath, str
        )
        triplestore_spec_path = get_config_param(
            config_graph, test_config_subject, MUSTRDTEST.triplestoreSpecPath, str
        )
        pytest_path = get_config_param(
            config_graph, test_config_subject, MUSTRDTEST.hasPytestPath, str
        )
        filter_on_tripleStore = tuple(
            config_graph.objects(
                subject=test_config_subject, predicate=MUSTRDTEST.filterOnTripleStore
            )
        )

        # Root path is the mustrd test config path
        root_path = Path(config_path).parent
        spec_path = root_path / Path(spec_path) if spec_path else None
        data_path = root_path / Path(data_path) if data_path else None
        triplestore_spec_path = (
            root_path / Path(triplestore_spec_path) if triplestore_spec_path else None
        )

        # hasOntologyPath may be repeated; each value is a file or a directory
        # (scanned recursively), resolved relative to the config file.
        ontology_paths = tuple(
            root_path / Path(str(o))
            for o in config_graph.objects(
                subject=test_config_subject, predicate=MUSTRDTEST.hasOntologyPath
            )
        )

        test_configs.append(
            TestConfig(
                spec_path=spec_path,
                data_path=data_path,
                triplestore_spec_path=triplestore_spec_path,
                pytest_path=pytest_path,
                filter_on_tripleStore=filter_on_tripleStore,
                ontology_paths=ontology_paths,
            )
        )
    return test_configs


def get_config_param(config_graph, config_subject, config_param, convert_function):
    raw_value = config_graph.value(
        subject=config_subject, predicate=config_param, any=True
    )
    return convert_function(raw_value) if raw_value else None


def _local_name(iri):
    """The local part of an IRI (after the last # or /), for display."""
    s = str(iri)
    for sep in ("#", "/"):
        if sep in s:
            s = s.rsplit(sep, 1)[-1]
    return s or str(iri)


def _github_blob_prefix():
    """In GitHub Actions, the '<server>/<repo>/blob/<sha>/' prefix for linking a
    repo file on the GitHub web UI; None when not running as an Action."""
    if os.environ.get("GITHUB_ACTIONS") != "true":
        return None
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com").rstrip("/")
    repo = os.environ.get("GITHUB_REPOSITORY")
    ref = os.environ.get("GITHUB_SHA") or os.environ.get("GITHUB_REF_NAME")
    if not (repo and ref):
        return None
    return f"{server}/{repo}/blob/{ref}/"


def _link_href(link_base):
    """Return a function mapping a source-file path to its report href.

    In a GitHub Actions run the job summary is rendered on the Actions page, where
    report-relative links don't resolve — so links become absolute URLs into the
    repo on the GitHub web UI (path taken relative to GITHUB_WORKSPACE). Otherwise
    they stay relative to `link_base` (the report dir for --md, the cwd for
    terminal output) so a Markdown previewer resolves them."""
    prefix = _github_blob_prefix()
    root = os.environ.get("GITHUB_WORKSPACE") or os.getcwd()

    def href(src):
        if not src or str(src) == "unknown.mustrd.ttl":
            return None
        src = str(src)
        if prefix:
            try:
                return prefix + os.path.relpath(src, root).replace(os.sep, "/")
            except ValueError:
                return None
        try:
            return os.path.relpath(src, link_base or ".")
        except ValueError:
            return src
    return href


def _link_report_refs(coverage, href):
    """Set the `link` (the href to the referencing spec file) on every spec
    reference in the report — undeclared-term refs, per-term cover refs, CQ-gap
    refs, duplicate-CQ nodes, and the TBox-in-data entries."""
    if not coverage:
        return
    ref_lists = [t.get("refs", []) for t in coverage.get("undeclared", [])]
    ref_lists += [t.get("cover_refs", []) for t in coverage.get("terms", [])]
    ref_lists += [t.get("non_cq_refs", []) for t in coverage.get("cq_gaps", [])]
    ref_lists += [d.get("cqs", []) for d in coverage.get("duplicate_cqs", [])]
    # TBox-in-data entries carry their own source_file/link directly.
    ref_lists += [coverage.get("tbox_in_data", [])]
    for refs in ref_lists:
        for ref in refs:
            ref["link"] = href(ref.get("source_file"))


@dataclass(frozen=True)
class TestConfig:
    spec_path: Path
    data_path: Path
    triplestore_spec_path: Path
    pytest_path: str
    filter_on_tripleStore: str = None
    ontology_paths: tuple = ()


# Configure logging - do not use setup_logger in the pytest plugin, 
# the CLI args to pytest (e.g. --log-cli-level) are overriden by it
logger = logging.getLogger(__name__)


class MustrdTestPlugin:
    md_path: str
    test_config_file: Path
    selected_tests: list
    secrets: str
    items: list
    path_filter: str
    collect_error: BaseException

    def __init__(self, md_path, test_config_file, secrets, ignore_focus=False,
                 term_coverage=False, cq=False, term_coverage_rdf=None):
        self.md_path = md_path
        self.test_config_file = test_config_file
        self.secrets = secrets
        self.ignore_focus = ignore_focus
        self.term_coverage = term_coverage
        self.cq = cq
        self.term_coverage_rdf = term_coverage_rdf
        self.ontology_paths = []
        self.items = []

    @pytest.hookimpl(tryfirst=True)
    def pytest_collection(self, session):
        logger.info("Starting test collection")

        args = session.config.args

        # Split args into mustrd and regular pytest args
        mustrd_args = [arg for arg in args if ".mustrd.ttl" in arg]
        pytest_args = [arg for arg in args if arg != os.getcwd() and ".mustrd.ttl" not in arg]

        self.selected_tests = list(
            map(
                lambda arg: Path(arg.split("::")[0]),
                mustrd_args
            )
        )
        logger.info(f"selected_tests is: {self.selected_tests}")

        self.path_filter = session.config.getoption("pytest_path") or None

        logger.info(f"path_filter is: {self.path_filter}")
        logger.info(f"Args: {args}")
        logger.info(f"Mustrd Args: {mustrd_args}")
        logger.info(f"Pytest Args: {pytest_args}")
        logger.info(f"Path Filter: {self.path_filter}")

        # Only modify args if we have mustrd tests to run
        if self.selected_tests:
            # Keep original pytest args and add config file for mustrd
            session.config.args = pytest_args + [str(self.test_config_file.resolve())]
        else:
            # Keep original args unchanged for regular pytest
            session.config.args = args

        logger.info(f"Final session.config.args: {session.config.args}")

        # Ontology term coverage needs an ontology to measure against. Resolve it
        # from the config now (and fail early with a helpful message if absent),
        # so the user is told before any tests run rather than after.
        if self.term_coverage or self.term_coverage_rdf:
            self._resolve_ontology_paths_or_fail()

    def _resolve_ontology_paths_or_fail(self):
        # Reuse parse_config (which also SHACL-validates) so ontology paths come
        # from the same TestConfig the tests are built from — one source of truth.
        config_path = Path(self.test_config_file)
        test_configs = parse_config(config_path)
        self.ontology_paths = [p for tc in test_configs for p in tc.ontology_paths]
        if not self.ontology_paths:
            raise pytest.UsageError(self._missing_ontology_message(config_path))

    def _missing_ontology_message(self, config_path):
        config_graph = Graph().parse(config_path)
        subjects = list(config_graph.subjects(RDF.type, MUSTRDTEST.MustrdTest))
        subj = subjects[0] if subjects else "https://your.example/mustrdTest/yourTest"
        return (
            "--term-coverage needs an ontology to measure against, but no "
            "mustrdTest:hasOntologyPath is set in the test configuration.\n"
            f"  Config file to amend: {config_path}\n"
            "  Add one or more ontology locations (a file, or a directory that "
            "is scanned recursively), e.g.:\n\n"
            f"      <{subj}> <https://mustrd.org/mustrdTest/hasOntologyPath> \"<insert ontology path here>\" .\n\n"
            "  The property may be repeated for multiple ontologies."
        )

    def get_file_name_from_arg(self, arg):
        if arg and len(arg) > 0 and "[" in arg and ".mustrd.ttl " in arg:
            return arg[arg.index("[") + 1: arg.index(".mustrd.ttl ")]
        return None

    @pytest.hookimpl
    def pytest_collect_file(self, parent, path):
        logger.debug(f"Collecting file: {path}")
        # Only collect .ttl files that are mustrd suite config files
        if not str(path).endswith('.ttl'):
            return None
        if Path(path).resolve() != Path(self.test_config_file).resolve():
            logger.debug(f"{self.test_config_file}: Skipping non-matching-config file: {path}")
            return None

        mustrd_file = MustrdFile.from_parent(parent, path=pathlib.Path(path), mustrd_plugin=self)
        mustrd_file.mustrd_plugin = self
        return mustrd_file

    # Generate test for each triple store available
    def generate_tests_for_config(self, config, triple_stores, file_name):
        logger.debug(f"generate_tests_for_config {config=} {self=} {dir(self)}")
        shacl_graph = Graph().parse(
            Path(os.path.join(mustrd_root, "model/mustrdShapes.ttl"))
        )
        ont_graph = Graph().parse(Path(os.path.join(mustrd_root, "model/ontology.ttl")))
        logger.debug("Generating tests for config: " + str(config))
        logger.debug(f"selected_tests {self.selected_tests}")

        valid_spec_uris, spec_graph, invalid_specs = validate_specs(
            config,
            triple_stores,
            shacl_graph,
            ont_graph,
            file_name or "*",
            selected_test_files=self.selected_tests,
            ignore_focus=self.ignore_focus,
        )
        logger.info(f"Valid spec URIs: {valid_spec_uris}")
        specs, skipped_spec_results = get_specs(
            valid_spec_uris, spec_graph, triple_stores, config
        )

        # Return normal specs + skipped results
        return specs + skipped_spec_results + invalid_specs

    # Get triple store configuration or default
    def get_triple_stores_from_file(self, test_config):
        if test_config.triplestore_spec_path:
            try:
                triple_stores = get_triple_stores(
                    get_triple_store_graph(
                        test_config.triplestore_spec_path, self.secrets
                    )
                )
            except Exception as e:
                print(
                    f"""Triplestore configuration parsing failed {test_config.triplestore_spec_path}.
                    Only rdflib will be executed""",
                    e,
                )
                triple_stores = [
                    {"type": TRIPLESTORE.RdfLib, "uri": TRIPLESTORE.RdfLib}
                ]
        else:
            print("No triple store configuration required: using embedded rdflib")
            triple_stores = [{"type": TRIPLESTORE.RdfLib, "uri": TRIPLESTORE.RdfLib}]

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

    # Hook function. Initialize the list of result in session
    def pytest_sessionstart(self, session):
        session.results = dict()

    # Hook function called each time a report is generated by a test
    # The report is added to a list in the session
    # so it can be used later in pytest_sessionfinish to generate the global report md file
    @pytest.hookimpl(tryfirst=True, hookwrapper=True)
    def pytest_runtest_makereport(self, item, call):
        outcome = yield
        result = outcome.get_result()

        if result.when == "call":
            # Add the result of the test to the session
            item.session.results[item] = result

    # Take all the test results in session, parse them, and generate the md file.
    def pytest_sessionfinish(self, session: Session, exitstatus):
        # --term-coverage-rdf also needs coverage computed (and an ontology).
        report_coverage = (self.term_coverage or bool(self.term_coverage_rdf)) \
            and bool(self.ontology_paths)
        report_cq = self.cq
        # Nothing to do unless we're writing an md report or reporting to stdout.
        if not self.md_path and not report_coverage and not report_cq:
            return

        test_results, all_specs, spec_by_uri, last_is_mustrd = \
            self._collect_results(session)

        # Competency questions are first-class cq:CompetencyQuestion nodes found
        # in the spec files; resolve their cq:cqSpec links against the collected
        # specs so a CQ can point at 0..n tests (or none at all).
        cq_defs = self._collect_cq_defs(spec_by_uri) if report_cq else []

        # The RDF graph is the CANONICAL run output; the whole report is rendered
        # from it. With an ontology it's the full coverage graph (with a CQ
        # overlay when --cq); with `--cq` alone it's a CQ-only graph (no
        # measurements). compute_coverage returns None if nothing is declared.
        coverage, ontology_graph, graph = \
            self._coverage(all_specs, cq_defs, report_cq) if report_coverage \
            else (None, None, None)
        if graph is None and report_cq:              # --cq with no ontology
            graph = cq_graph(cq_facts(cq_defs), **self._run_ident())

        # Markdown report. With --term-coverage and/or --cq it is the assembled
        # report; otherwise --md keeps its pre-existing form: a ResultList of
        # every test.
        if self.md_path:
            if report_coverage or report_cq:
                md = self._build_report(graph, ontology_graph, coverage,
                                        os.path.dirname(self.md_path) or ".")
            else:
                md = self._render_result_list(test_results, last_is_mustrd)
            parent = os.path.dirname(self.md_path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(self.md_path, "w", encoding="utf-8") as file:
                file.write(md)

        # RDF output (--term-coverage-rdf), for a knowledge graph.
        if self.term_coverage_rdf and graph is not None:
            parent = os.path.dirname(self.term_coverage_rdf)
            if parent:
                os.makedirs(parent, exist_ok=True)
            graph.serialize(destination=self.term_coverage_rdf, format="turtle")

        # To stdout — only for the human-facing flags (not RDF-only runs).
        if self.term_coverage or report_cq:
            body = self._build_report(graph, ontology_graph, coverage, os.getcwd())
            self._report_to_terminal(session.config, body)

    def _coverage(self, all_specs, cq_defs, report_cq):
        """Compute coverage and build its canonical RDF graph. Returns
        (coverage_dict, ontology_graph, graph); (None, None, None) on failure or
        when nothing is declared."""
        try:
            ontology_graph = load_ontology(self.ontology_paths)
            coverage = compute_coverage(all_specs, ontology=ontology_graph,
                                        cq_defs=cq_defs if report_cq else None)
            if coverage is None:
                return None, None, None
            return coverage, ontology_graph, self._coverage_graph(coverage)
        except Exception as e:
            logger.warning(f"Could not compute ontology term coverage: {e}")
            return None, None, None

    @staticmethod
    def _run_ident():
        """run_slug / commit / mustrd_version for a graph, from the CI env."""
        sha = os.environ.get("GITHUB_SHA")
        server = os.environ.get("GITHUB_SERVER_URL", "https://github.com").rstrip("/")
        repo = os.environ.get("GITHUB_REPOSITORY")
        try:
            from importlib.metadata import version, PackageNotFoundError
            try:
                mustrd_version = version("mustrd")
            except PackageNotFoundError:
                mustrd_version = None
        except Exception:
            mustrd_version = None
        return {"run_slug": sha or "local",
                "commit": f"{server}/{repo}/commit/{sha}" if (sha and repo) else None,
                "mustrd_version": mustrd_version}

    def _coverage_graph(self, coverage):
        """Build the canonical coverage RDF graph."""
        ontologies = [{"uri": r["uri"], "version": r.get("version"),
                       "description": r.get("description"), "path": r.get("path")}
                      for r in ontology_report(self.ontology_paths) if r.get("uri")]
        return coverage_graph(coverage, ontologies, **self._run_ident())

    def _collect_results(self, session):
        """Build a TestResult for every test (for the ResultList --md) and the
        mustrd-spec dicts (all of them — coverage is over all tests), plus a
        spec-IRI → spec-dict map so competency questions can resolve their
        cq:cqSpec links.
        Returns (test_results, all_specs, spec_by_uri, last_is_mustrd)."""
        test_results, all_specs, spec_by_uri = [], [], {}
        is_mustrd = False
        for test_conf, result in session.results.items():
            # Case auto generated tests
            if test_conf.originalname != test_conf.name:
                module_name = test_conf.parent.name
                class_name = test_conf.originalname
                test_name = (
                    test_conf.name.replace(class_name, "")
                    .replace("[", "")
                    .replace("]", "")
                )
                is_mustrd = True
            # Case normal unit tests
            else:
                module_name = test_conf.parent.parent.name
                class_name = test_conf.parent.name
                test_name = test_conf.originalname
                is_mustrd = False

            spec = getattr(test_conf, 'spec', None)
            test_result = TestResult(
                test_name, class_name, module_name, result.outcome, is_mustrd,
            )
            test_results.append(test_result)

            if spec is not None:
                cspec = self._coverage_spec(spec, result, test_name)
                all_specs.append(cspec)
                if cspec.get("uri"):
                    spec_by_uri[cspec["uri"]] = cspec
        return test_results, all_specs, spec_by_uri, is_mustrd

    @staticmethod
    def _coverage_spec(spec, result, test_name):
        when = getattr(spec, 'when', None)
        # `when` may be a single WhenSpec or a list of them.
        when_list = when if isinstance(when, list) else ([when] if when is not None else [])
        queries = [w.value for w in when_list if isinstance(getattr(w, 'value', None), str)]
        uri = getattr(spec, 'spec_uri', None)
        return {
            "name": getattr(spec, 'spec_file_name', test_name),
            "uri": str(uri) if uri is not None else None,
            "passed": result.outcome == "passed",
            "given": getattr(spec, 'given', None),
            "queries": queries,
            "source_file": getattr(spec, 'spec_source_file', None),
        }

    def _collect_cq_defs(self, spec_by_uri):
        """Find every cq:CompetencyQuestion node in the suite's spec files and
        resolve its cq:cqSpec links. A CQ may live in any *.mustrd.ttl under a
        config's hasSpecPath, and may point at 0..n specs (or none). Unresolvable
        cqSpec targets are kept in `missing_specs` so the table can flag them.
        Returns [{id, name, question, questions, source_file, specs, missing_specs}]."""
        try:
            spec_paths = [tc.spec_path for tc in parse_config(Path(self.test_config_file))
                          if tc.spec_path]
        except Exception as e:
            logger.warning(f"Could not read spec paths for competency questions: {e}")
            return []
        defs, seen = [], set()
        for sp in spec_paths:
            for ttl in sorted(Path(sp).glob("**/*.mustrd.ttl")):
                g = Graph()
                try:
                    g.parse(ttl)
                except Exception:
                    continue
                for cq in g.subjects(RDF.type, CQ.CompetencyQuestion):
                    cid = str(cq)
                    if cid in seen:
                        continue
                    seen.add(cid)
                    questions = [str(o) for o in g.objects(cq, CQ.question)]
                    specs, missing = [], []
                    for u in (str(o) for o in g.objects(cq, CQ.cqSpec)):
                        (specs.append(spec_by_uri[u]) if u in spec_by_uri
                         else missing.append(u))
                    defs.append({
                        "id": cid, "name": _local_name(cid),
                        "question": questions[0] if questions else None,
                        "questions": questions, "source_file": str(ttl),
                        "specs": specs, "missing_specs": missing,
                    })
        return sorted(defs, key=lambda d: (d.get("question") or "", d["name"]))

    @staticmethod
    def _render_result_list(test_results, is_mustrd):
        """The pre-existing (master) --md report: a ResultList of every test."""
        result_list = ResultList(
            None,
            get_result_list(
                test_results,
                lambda result: result.type,
                lambda result: is_mustrd and result.test_name.split("@")[1],
            ),
            False,
        )
        return result_list.render()

    def _build_report(self, graph, ontology_graph, coverage, link_base):
        """Assemble the report, rendered entirely FROM the RDF graph (+ the
        ontology for the subClassOf tree). Two H2 sub-reports under a top title:

          # Ontologies Report
          ## Coverage Report              (when an ontology was checked)
          ## Competency Questions Report  (--cq)
        """
        parts = []
        href = _link_href(link_base)
        if coverage is not None and graph is not None and ontology_graph is not None:
            ctx = coverage_context(graph, ontology_graph)
            _link_report_refs(ctx, href)
            parts.append("# Ontologies Report")
            parts.append("## Coverage Report")
            ontologies = read_ontologies(graph)
            for o in ontologies:
                o["url"] = href(o["path"])
            if ontologies:
                parts.append(render_ontologies(ontologies))
            parts.append(render_term_coverage(ctx))
            if ctx.get("tbox_in_data"):
                parts.append(render_tbox_in_data(ctx["tbox_in_data"]))
        if self.cq and graph is not None:
            cqr = cq_report(graph, ontology_graph, href)
            parts.append("## Competency Questions Report" if coverage is not None
                         else "# Competency Questions Report")
            parts.append(render_cq_table(cqr["per_cq"], show_coverage=cqr["has_ontology"]))
            if cqr["duplicate_cqs"]:
                parts.append(render_duplicate_cqs(cqr["duplicate_cqs"]))
            if cqr["has_ontology"]:
                parts.append(render_cq_gaps(cqr["cq_gaps"]))
            if cqr["per_cq"]:
                parts.append(render_per_cq(cqr["per_cq"], unchecked=not cqr["has_ontology"]))
        return "\n\n".join(parts)

    def _report_to_terminal(self, config, body):
        tr = config.pluginmanager.get_plugin("terminalreporter")
        lines = (body or "No competency questions or ontology coverage to report.").splitlines()
        if tr is not None:
            tr.section("Mustrd report", sep="=")
            for line in lines:
                tr.write_line(line)
        else:  # pragma: no cover - terminalreporter is normally present
            print("\n".join(lines))


class MustrdFile(pytest.File):
    mustrd_plugin: MustrdTestPlugin

    def __init__(self, *args, mustrd_plugin, **kwargs):
        logger.debug(f"Creating MustrdFile with args: {args}, kwargs: {kwargs}")
        self.mustrd_plugin = mustrd_plugin
        super(pytest.File, self).__init__(*args, **kwargs)

    def collect(self):
        try:
            logger.info(f"{self.mustrd_plugin.test_config_file}: Collecting tests from file: {self.path=}")
            # Only process the specific mustrd config file we were given

            # if not str(self.fspath).endswith(".ttl"):
            #     return []
            # Only process the specific mustrd config file we were given
            # if str(self.fspath) != str(self.mustrd_plugin.test_config_file):
            #     logger.info(f"Skipping non-config file: {self.fspath}")
            #     return []

            test_configs = parse_config(self.path)
            from collections import defaultdict
            pytest_path_grouped = defaultdict(list)
            for test_config in test_configs:
                if (
                    self.mustrd_plugin.path_filter is not None
                    and not str(test_config.pytest_path).startswith(str(self.mustrd_plugin.path_filter))
                ):
                    logger.info(f"Skipping test config due to path filter: {test_config.pytest_path=} {self.mustrd_plugin.path_filter=}")
                    continue

                triple_stores = self.mustrd_plugin.get_triple_stores_from_file(test_config)
                try:
                    specs = self.mustrd_plugin.generate_tests_for_config(
                        {
                            "spec_path": test_config.spec_path,
                            "data_path": test_config.data_path,
                        },
                        triple_stores,
                        None,
                    )
                except Exception as e:
                    logger.error(f"Error generating tests: {e}\n{traceback.format_exc()}")
                    specs = [
                        SpecInvalid(
                            MUST.TestSpec,
                            triple_store["uri"] if isinstance(triple_store, dict) else triple_store,
                            f"Test generation failed: {str(e)}",
                            spec_file_name=str(test_config.spec_path.name) if test_config.spec_path else "unknown.mustrd.ttl",
                            spec_source_file=self.path if test_config.spec_path else Path("unknown.mustrd.ttl"),
                        )
                        for triple_store in (triple_stores or test_config.filter_on_tripleStore)
                    ]
                pytest_path = getattr(test_config, "pytest_path", "unknown")
                for spec in specs:
                    pytest_path_grouped[pytest_path].append(spec)

            for pytest_path, specs_for_path in pytest_path_grouped.items():
                logger.info(f"pytest_path group: {pytest_path} ({len(specs_for_path)} specs)")

                yield MustrdPytestPathCollector.from_parent(
                    self,
                    name=str(pytest_path),
                    pytest_path=pytest_path,
                    specs=specs_for_path,
                    mustrd_plugin=self.mustrd_plugin,
                )
        except Exception as e:
            self.mustrd_plugin.collect_error = e
            logger.error(f"Error during collection {self.path}: {type(e)} {e} {traceback.format_exc()}")
            raise e


class MustrdPytestPathCollector(pytest.Class):
    def __init__(self, name, parent, pytest_path, specs, mustrd_plugin):
        super().__init__(name, parent)
        self.pytest_path = pytest_path
        self.specs = specs
        self.mustrd_plugin = mustrd_plugin

    def collect(self):
        for spec in self.specs:
            item = MustrdItem.from_parent(
                self,
                name=spec.spec_file_name,
                spec=spec,
            )
            self.mustrd_plugin.items.append(item)
            yield item


class MustrdItem(pytest.Item):
    def __init__(self, name, parent, spec):
        logging.debug(f"Creating item: {name}")
        super().__init__(name, parent)
        self.spec = spec
        self.fspath = spec.spec_source_file
        self.originalname = name

    def runtest(self):
        result = run_test_spec(self.spec)
        if not result:
            raise AssertionError(f"Test {self.name} failed")

    def repr_failure(self, excinfo):
        # excinfo.value is the exception instance
        # You can add more context here
        tb_lines = traceback.format_exception(excinfo.type, excinfo.value, excinfo.tb)
        tb_str = "".join(tb_lines)
        return (
            f"{self.name} failed:\n"
            f"Spec: {self.spec.spec_uri}\n"
            f"File: {self.spec.spec_source_file}\n"
            f"Error: \n{excinfo.value}\n"
            f"Traceback:\n{tb_str}"
        )

    def reportinfo(self):
        r = "", 0, f"mustrd test: {self.name}"
        return r


# Function called in the test to actually run it
def run_test_spec(test_spec):
    logger = logging.getLogger("mustrd.test")
    logger.info(f"Running test spec: {getattr(test_spec, 'spec_uri', test_spec)}")
    try:
        result = run_spec(test_spec)
        logger.info(f"Result type: {type(result)} for spec: {getattr(test_spec, 'spec_uri', test_spec)}")
    except Exception as e:
        logger.error(f"Exception in run_spec for {getattr(test_spec, 'spec_uri', test_spec)}: {e}")
        logger.error(traceback.format_exc())
        raise  # re-raise so pytest sees the error

    if isinstance(test_spec, SpecInvalid):
        logger.error(f"Invalid test specification: {test_spec.message} {test_spec}")
        pytest.fail(f"Invalid test specification: {test_spec.message} {test_spec}")
    if not isinstance(result, SpecPassed):
        write_result_diff_to_log(result, logger.info)
        log_lines = []

        def log_to_string(message):
            log_lines.append(message)
        try:
            write_result_diff_to_log(result, log_to_string)
        except Exception as e:
            logger.error(f"Exception in write_result_diff_to_log: {e}")
            logger.error(traceback.format_exc())
        logger.error(f"Test failed: {log_lines}")
        raise AssertionError("Test failed: " + "\n".join(log_lines))

    logger.info(f"Test PASSED: {getattr(test_spec, 'spec_uri', test_spec)}")
    return isinstance(result, SpecPassed)
