import logging
from dataclasses import dataclass
import pytest
import os
from pathlib import Path, PosixPath
from rdflib.namespace import Namespace
from rdflib import Graph, RDF
from pytest import Session

from mustrd import logger_setup
from mustrd.TestResult import ResultList, TestResult, get_result_list
from mustrd.utils import get_mustrd_root
from mustrd.mustrd import (
    write_result_diff_to_log,
    get_triple_store_graph,
    get_triple_stores,
)
from mustrd.mustrd import (
    Specification,
    SpecSkipped,
    validate_specs,
    get_specs,
    SpecPassed,
    run_spec,
)
from mustrd.namespace import MUST, TRIPLESTORE, MUSTRDTEST
from typing import Union
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
    return


def pytest_configure(config) -> None:
    # Read configuration file
    if config.getoption("mustrd") and config.getoption("configpath"):
        config.pluginmanager.register(
            MustrdTestPlugin(
                config.getoption("mdpath"),
                Path(config.getoption("configpath")),
                config.getoption("secrets"),
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

        test_configs.append(
            TestConfig(
                spec_path=spec_path,
                data_path=data_path,
                triplestore_spec_path=triplestore_spec_path,
                pytest_path=pytest_path,
                filter_on_tripleStore=filter_on_tripleStore,
            )
        )
    return test_configs


def get_config_param(config_graph, config_subject, config_param, convert_function):
    raw_value = config_graph.value(
        subject=config_subject, predicate=config_param, any=True
    )
    return convert_function(raw_value) if raw_value else None


@dataclass(frozen=True)
class TestConfig:
    spec_path: Path
    data_path: Path
    triplestore_spec_path: Path
    pytest_path: str
    filter_on_tripleStore: str = None


@dataclass(frozen=True)
class TestParamWrapper:
    id: str
    test_config: TestConfig
    unit_test: Union[Specification, SpecSkipped]


# Configure logging
logger = logger_setup.setup_logger(__name__)


class MustrdTestPlugin:
    md_path: str
    test_config_file: Path
    selected_tests: list
    secrets: str
    unit_tests: Union[Specification, SpecSkipped]
    items: list
    path_filter: str
    collect_error: BaseException

    def __init__(self, md_path, test_config_file, secrets):
        self.md_path = md_path
        self.test_config_file = test_config_file
        self.secrets = secrets
        self.items = []

    @pytest.hookimpl(tryfirst=True)
    def pytest_collection(self, session):
        logger.info("Starting test collection")
        
        self.unit_tests = []
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

    def get_file_name_from_arg(self, arg):
        if arg and len(arg) > 0 and "[" in arg and ".mustrd.ttl " in arg:
            return arg[arg.index("[") + 1 : arg.index(".mustrd.ttl ")]
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

        valid_spec_uris, spec_graph, invalid_spec_results = validate_specs(
            config,
            triple_stores,
            shacl_graph,
            ont_graph,
            file_name or "*",
            selected_test_files=self.selected_tests,
        )
        # Convert invalid specs to SpecInvalid instead of SpecSkipped
        invalid_specs = [
            SpecInvalid(
                spec.spec_uri,
                spec.triple_store,
                spec.message,
                spec.spec_file_name,
                spec.spec_source_file
            ) for spec in invalid_spec_results
        ]


        specs, skipped_spec_results = get_specs(
            valid_spec_uris, spec_graph, triple_stores, config
        )

        # Return normal specs + skipped results
        return specs + skipped_spec_results + invalid_specs

    # Function called to generate the name of the test
    def get_test_name(self, spec):
        # FIXME: SpecSkipped should have the same structure?
        if isinstance(spec, SpecSkipped):
            triple_store = spec.triple_store
        else:
            triple_store = spec.triple_store["type"]

        triple_store_name = triple_store.replace("https://mustrd.com/model/", "")
        test_name = spec.spec_uri.replace(spnamespace, "").replace("_", " ")
        return spec.spec_file_name + " : " + triple_store_name + ": " + test_name

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

    # Take all the test results in session, parse them, split them in mustrd and standard pytest  and generate md file
    def pytest_sessionfinish(self, session: Session, exitstatus):
        # if md path has not been defined in argument, then do not generate md file
        if not self.md_path:
            return

        test_results = []
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

            test_results.append(
                TestResult(
                    test_name, class_name, module_name, result.outcome, is_mustrd
                )
            )

        result_list = ResultList(
            None,
            get_result_list(
                test_results,
                lambda result: result.type,
                lambda result: is_mustrd and result.test_name.split("@")[1],
            ),
            False,
        )

        md = result_list.render()
        with open(self.md_path, "w") as file:
            file.write(md)

@dataclass(frozen=True)
class SpecInvalid:
    spec_uri: str
    triple_store: str
    message: str
    spec_file_name: str = None
    spec_source_file: Path = None

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
    if isinstance(test_spec, SpecSkipped):
        logger.warning(f"Test skipped: {test_spec.message}")
        pytest.skip(f"Invalid configuration, error : {test_spec.message}")
    try:
        result = run_spec(test_spec)
        logger.info(f"Result type: {type(result)} for spec: {getattr(test_spec, 'spec_uri', test_spec)}")
    except Exception as e:
        logger.error(f"Exception in run_spec for {getattr(test_spec, 'spec_uri', test_spec)}: {e}")
        logger.error(traceback.format_exc())
        raise  # re-raise so pytest sees the error

    if isinstance(test_spec, SpecInvalid):
        logger.error(f"Invalid test specification: {test_spec.message} {test_spec}")
        raise ValueError(f"Invalid test specification: {test_spec.message} {test_spec}")
    if type(result) == SpecSkipped:
        logger.warning("Test skipped due to unsupported configuration")
        pytest.skip("Unsupported configuration")
    if type(result) != SpecPassed:
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
    return type(result) == SpecPassed
