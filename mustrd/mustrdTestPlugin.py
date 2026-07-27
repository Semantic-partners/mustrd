import logging
import pytest
import os
from pathlib import Path
from rdflib.namespace import Namespace
from rdflib import Graph, RDF
from pytest import Session

from mustrd.TestResult import TestResult
from mustrd.reporting import (
    ReportOptions, wants_coverage, wants_cq, produce_report, collect_cq_defs,
    coverage_spec,
)
from mustrd.runner import generate_specs, resolve_triple_stores
# TestConfig / parse_config moved to mustrd.config (no pytest dependency, so the
# CLI shares them); re-exported here for callers that import them from the plugin.
from mustrd.config import TestConfig, parse_config, get_config_param  # noqa: F401
from mustrd.results_rdf import RunResult
# re-exported so `from mustrd.mustrdTestPlugin import _link_href, ...` keeps
# working for existing callers/tests after the extraction into reporting.py
from mustrd.reporting import _link_href, _link_report_refs  # noqa: F401
from mustrd.utils import get_mustrd_root
from mustrd.mustrd import (
    SpecPassed,
    run_spec,
    write_result_diff_to_log,
    SpecInvalid
)
from mustrd.namespace import MUST, MUSTRDTEST

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
    group.addoption(
        "--term-coverage-jsonld",
        action="store",
        dest="term_coverage_jsonld",
        metavar="pathToJsonLd",
        default=None,
        help="Write the coverage graph as JSON-LD to this path, for the "
             "standalone results viewer. Same graph as --term-coverage-rdf.",
    )
    group.addoption(
        "--results-rdf",
        action="store",
        dest="results_rdf",
        metavar="pathToRdf",
        default=None,
        help="Write per-test results (every test, passed/failed/skipped, with "
             "timing) as RDF Turtle to this path.",
    )
    group.addoption(
        "--results-jsonld",
        action="store",
        dest="results_jsonld",
        metavar="pathToJsonLd",
        default=None,
        help="Write per-test results as JSON-LD to this path, for the "
             "standalone results viewer's Playwright-style test tree.",
    )
    group.addoption(
        "--viewer",
        action="store",
        dest="viewer",
        metavar="pathToHtml",
        default=None,
        help="Write a self-contained HTML report to this path: one file, no "
             "dependencies, with the run's RDF inlined and rendered in the browser "
             "(tests, coverage, competency questions, issues).",
    )
    group.addoption(
        "--viewer-title",
        action="store",
        dest="viewer_title",
        metavar="title",
        default="mustrd run report",
        help="Page title for --viewer.",
    )
    group.addoption(
        "--no-viewer-sources",
        action="store_false",
        dest="viewer_sources",
        default=True,
        help="Do not inline each spec's Turtle and SPARQL into the --viewer page. "
             "They are included by default so the report is readable without the "
             "files it was generated from; this keeps the page smaller.",
    )
    group.addoption(
        "--viewer-src-base",
        action="store",
        dest="viewer_src_base",
        metavar="prefix",
        default=None,
        help="Prefix for the viewer's spec/ontology source links. The graph stores "
             "paths relative to the working directory, so set this when the page is "
             "served from somewhere else (e.g. '../' for a report/ subdir). Defaults "
             "to the GitHub blob URL in Actions.",
    )
    group.addoption(
        "--term-links",
        action="store",
        dest="term_links",
        metavar="off|file|iri",
        choices=("off", "file", "iri"),
        default="off",
        help="Linkify terms in the coverage report. 'file' deep-links each term "
             "to its declaration in the ontology source (path#Lline), for local "
             "browsing; 'iri' links to the term's full IRI, for environments "
             "where it HTTP-resolves; 'off' (default) leaves terms as plain text.",
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
                config.getoption("term_links"),
                term_coverage_jsonld=config.getoption("term_coverage_jsonld"),
                results_rdf=config.getoption("results_rdf"),
                results_jsonld=config.getoption("results_jsonld"),
                viewer=config.getoption("viewer"),
                viewer_title=config.getoption("viewer_title"),
                viewer_src_base=config.getoption("viewer_src_base"),
                viewer_sources=config.getoption("viewer_sources"),
            )
        )


# No logging configuration in the plugin: under pytest, pytest is the
# application, and configuring anything here overrides its options
# (--log-cli-level and friends). See mustrd.logger_setup.
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
                 term_coverage=False, cq=False, term_coverage_rdf=None, term_links="off",
                 term_coverage_jsonld=None, results_rdf=None, results_jsonld=None,
                 viewer=None, viewer_title="mustrd run report",
                 viewer_src_base=None, viewer_sources=True):
        self.md_path = md_path
        self.test_config_file = test_config_file
        self.secrets = secrets
        self.ignore_focus = ignore_focus
        self.term_coverage = term_coverage
        self.cq = cq
        self.term_coverage_rdf = term_coverage_rdf
        self.term_coverage_jsonld = term_coverage_jsonld
        self.results_rdf = results_rdf
        self.results_jsonld = results_jsonld
        self.viewer = viewer
        self.viewer_title = viewer_title
        self.viewer_src_base = viewer_src_base
        self.viewer_sources = viewer_sources
        self.term_links = term_links
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
        elif self.viewer:
            # The viewer shows a Coverage tab when the config declares an ontology,
            # but a results-only viewer is perfectly useful — so resolve the paths
            # without insisting on them.
            self._resolve_ontology_paths()

    def _resolve_ontology_paths(self):
        # Reuse parse_config (which also SHACL-validates) so ontology paths come
        # from the same TestConfig the tests are built from — one source of truth.
        test_configs = parse_config(Path(self.test_config_file))
        self.ontology_paths = [p for tc in test_configs for p in tc.ontology_paths]
        return self.ontology_paths

    def _resolve_ontology_paths_or_fail(self):
        if not self._resolve_ontology_paths():
            raise pytest.UsageError(
                self._missing_ontology_message(Path(self.test_config_file)))

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
        logger.debug(f"selected_tests {self.selected_tests}")
        # Shared with the `mustrd` CLI (see runner.py) so both build identical
        # specs from the same config.
        specs, skipped = generate_specs(
            config, triple_stores, file_name,
            selected_tests=self.selected_tests, ignore_focus=self.ignore_focus,
        )
        return specs + skipped

    # Get triple store configuration or default
    def get_triple_stores_from_file(self, test_config):
        return resolve_triple_stores(test_config, self.secrets)

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
        elif result.when == "setup" and result.outcome == "skipped":
            # A skipped test never reaches the call phase, so without this it would
            # be absent from the results graph entirely rather than reported as
            # skipped. A setup report that passed is ignored — the call report
            # that follows carries the real outcome.
            item.session.results[item] = result

    # Take all the test results in session, parse them, and generate the md file.
    def pytest_sessionfinish(self, session: Session, exitstatus):
        opts = ReportOptions(
            md_path=self.md_path, term_coverage=self.term_coverage, cq=self.cq,
            term_coverage_rdf=self.term_coverage_rdf,
            term_coverage_jsonld=self.term_coverage_jsonld,
            results_rdf=self.results_rdf, results_jsonld=self.results_jsonld,
            viewer=self.viewer, viewer_title=self.viewer_title,
            viewer_src_base=self.viewer_src_base,
            viewer_sources=self.viewer_sources,
            term_links=self.term_links, ontology_paths=tuple(self.ontology_paths),
        )
        report_coverage = wants_coverage(opts)
        report_cq = wants_cq(opts)
        want_results = bool(opts.results_rdf or opts.results_jsonld)
        # Nothing to do unless we're writing a report, RDF, a viewer, or stdout.
        if not (opts.md_path or report_coverage or report_cq or want_results
                or opts.term_coverage_jsonld or opts.viewer):
            return

        test_results, all_specs, spec_by_uri, last_is_mustrd, run_results = \
            self._collect_results(session)

        # Competency questions are first-class cq:CompetencyQuestion nodes found
        # in the spec files; resolve their cq:cqSpec links against the collected
        # specs so a CQ can point at 0..n tests (or none at all).
        cq_defs = self._collect_cq_defs(spec_by_uri) if report_cq else []

        # Compute the canonical RDF graph, write the reports/serializations, and
        # emit the terminal body — all in the shared reporting library, so the
        # `mustrd` CLI and this plugin produce identical output.
        produce_report(
            all_specs, cq_defs, test_results, last_is_mustrd, opts,
            terminal_writer=lambda body: self._report_to_terminal(session.config, body),
            run_results=run_results,
        )

    def _collect_results(self, session):
        """Build a TestResult for every test (for the ResultList --md) and the
        mustrd-spec dicts (all of them — coverage is over all tests), plus a
        spec-IRI → spec-dict map so competency questions can resolve their
        cq:cqSpec links.
        Returns (test_results, all_specs, spec_by_uri, last_is_mustrd, run_results)."""
        test_results, all_specs, spec_by_uri, run_results = [], [], {}, []
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

            spec_uri = getattr(spec, 'spec_uri', None) if spec is not None else None
            spec_src = getattr(spec, 'spec_source_file', None) if spec is not None else None
            run_results.append(RunResult(
                status=result.outcome,
                test_type="mustrd" if is_mustrd else "pytest",
                module=module_name, class_name=class_name, test_name=test_name,
                spec_uri=str(spec_uri) if spec_uri is not None else None,
                spec_file_name=getattr(spec, 'spec_file_name', None) if spec is not None else None,
                source_file=str(spec_src) if spec_src is not None else None,
                duration=getattr(result, 'duration', None),
            ))

            if spec is not None:
                cspec = coverage_spec(spec, result.outcome, test_name)
                all_specs.append(cspec)
                if cspec.get("uri"):
                    spec_by_uri[cspec["uri"]] = cspec
        return test_results, all_specs, spec_by_uri, is_mustrd, run_results

    def _collect_cq_defs(self, spec_by_uri):
        """Resolve the suite's competency questions (pytest-side wrapper): read
        the spec paths from the test config, then delegate to the shared
        reporting.collect_cq_defs to find/resolve the cq:CompetencyQuestion nodes."""
        try:
            spec_paths = [tc.spec_path for tc in parse_config(Path(self.test_config_file))
                          if tc.spec_path]
        except Exception as e:
            logger.warning(f"Could not read spec paths for competency questions: {e}")
            return []
        return collect_cq_defs(spec_paths, spec_by_uri)

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
