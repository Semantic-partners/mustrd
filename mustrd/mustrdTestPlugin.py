"""
MIT License

Copyright (c) 2023 Semantic Partners Ltd

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

from dataclasses import dataclass
import pytest
import os
from pathlib import Path
from rdflib.namespace import Namespace
from rdflib import Graph, RDF
from pytest import Session

from mustrd.TestResult import ResultList, TestResult, get_result_list
from mustrd.utils import get_mustrd_root
from mustrd.mustrd import get_triple_store_graph, get_triple_stores
from mustrd.mustrd import Specification, SpecSkipped, validate_specs, get_specs, SpecPassed, run_spec
from mustrd.namespace import MUST, TRIPLESTORE, MUSTRDTEST
from typing import Union
from pyshacl import validate

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
    return


def pytest_configure(config) -> None:
    # Read configuration file
    if config.getoption("mustrd"):
        test_configs = parse_config(config.getoption("configpath"))
        config.pluginmanager.register(MustrdTestPlugin(config.getoption("mdpath"),
                                                       test_configs, config.getoption("secrets")))


def parse_config(config_path):
    test_configs = []
    config_graph = Graph().parse(config_path)
    shacl_graph = Graph().parse(Path(os.path.join(mustrd_root, "model/mustrdTestShapes.ttl")))
    ont_graph = Graph().parse(Path(os.path.join(mustrd_root, "model/mustrdTestOntology.ttl")))
    conforms, results_graph, results_text = validate(
            data_graph=config_graph,
            shacl_graph=shacl_graph,
            ont_graph=ont_graph,
            advanced=True,
            inference='none'
        )
    if not conforms:
        raise ValueError(f"Mustrd test configuration not conform to the shapes. SHACL report: {results_text}",
                         results_graph)

    for test_config_subject in config_graph.subjects(predicate=RDF.type, object=MUSTRDTEST.MustrdTest):
        spec_path = get_config_param(config_graph, test_config_subject, MUSTRDTEST.hasSpecPath, str)
        data_path = get_config_param(config_graph, test_config_subject, MUSTRDTEST.hasDataPath, str)
        triplestore_spec_path = get_config_param(config_graph, test_config_subject, MUSTRDTEST.triplestoreSpecPath, str)
        pytest_path = get_config_param(config_graph, test_config_subject, MUSTRDTEST.hasPytestPath, str)
        filter_on_tripleStore = list(config_graph.objects(subject=test_config_subject,
                                                          predicate=MUSTRDTEST.filterOnTripleStore))

        # Root path is the mustrd test config path
        root_path = Path(config_path).parent
        spec_path = root_path / Path(spec_path) if spec_path else None
        data_path = root_path / Path(data_path) if data_path else None
        triplestore_spec_path = root_path / Path(triplestore_spec_path) if triplestore_spec_path else None

        test_configs.append(TestConfig(spec_path=spec_path, data_path=data_path,
                                       triplestore_spec_path=triplestore_spec_path,
                                       pytest_path=pytest_path,
                                       filter_on_tripleStore=filter_on_tripleStore))
    return test_configs


def get_config_param(config_graph, config_subject, config_param, convert_function):
    raw_value = config_graph.value(subject=config_subject, predicate=config_param, any=True)
    return convert_function(raw_value) if raw_value else None


@dataclass
class TestConfig:
    spec_path: Path
    data_path: Path
    triplestore_spec_path: Path
    pytest_path: str
    filter_on_tripleStore: str = None


@dataclass
class TestParamWrapper:
    test_config: TestConfig
    unit_test: Union[Specification, SpecSkipped]


class MustrdTestPlugin:
    md_path: str
    test_configs: list
    secrets: str
    unit_tests: Union[Specification, SpecSkipped]
    items: list

    def __init__(self, md_path, test_configs, secrets):
        self.md_path = md_path
        self.test_configs = test_configs
        self.secrets = secrets
        self.items = []

    @pytest.hookimpl(tryfirst=True)
    def pytest_collection(self, session):
        self.unit_tests = []
        args = session.config.args
        if len(args) > 0:
            file_name = self.get_file_name_from_arg(args[0])
            # Filter test to collect only specified path
            config_to_collect = list(filter(lambda config:
                                            # Case we want to collect everything
                                            MUSTRD_PYTEST_PATH not in args[0]
                                            # Case we want to collect a test or sub test
                                            or (config.pytest_path or "") in args[0]
                                            # Case we want to collect a whole test folder
                                            or args[0].replace(f"./{MUSTRD_PYTEST_PATH}", "") in config.pytest_path,
                                            self.test_configs))

            # Redirect everything to test_mustrd.py,
            # no need to filter on specified test: Only specified test will be collected anyway
            session.config.args[0] = os.path.join(mustrd_root, "test/test_mustrd.py")
        # Collecting only relevant tests

        for one_test_config in config_to_collect:
            triple_stores = self.get_triple_stores_from_file(one_test_config)

            if one_test_config.filter_on_tripleStore and not triple_stores:
                self.unit_tests.extend(list(map(
                    lambda triple_store:
                        TestParamWrapper(test_config=one_test_config,
                                         unit_test=SpecSkipped(MUST.TestSpec, triple_store, "No triplestore found")),
                        one_test_config.filter_on_tripleStore)))
            else:
                specs = self.generate_tests_for_config({"spec_path": one_test_config.spec_path,
                                                        "data_path": one_test_config.data_path},
                                                       triple_stores, file_name)
                self.unit_tests.extend(list(map(
                    lambda spec: TestParamWrapper(test_config=one_test_config, unit_test=spec), specs)))

    def get_file_name_from_arg(self, arg):
        if arg and len(arg) > 0 and "[" in arg and ".mustrd.ttl@" in arg:
            return arg[arg.index("[") + 1: arg.index(".mustrd.ttl@")]
        return None

    @pytest.hookimpl(hookwrapper=True)
    def pytest_pycollect_makeitem(self, collector, name, obj):
        report = yield
        if name == "test_unit":
            items = report.get_result()
            new_results = []
            for item in items:
                virtual_path = MUSTRD_PYTEST_PATH + (item.callspec.params["unit_tests"].test_config.pytest_path or "default")
                item.fspath = Path(virtual_path)
                item._nodeid = virtual_path + "::" + item.name
                self.items.append(item)
                new_results.append(item)
            return new_results

    # Hook called at collection time: reads the configuration of the tests, and generate pytests from it
    def pytest_generate_tests(self, metafunc):
        if len(metafunc.fixturenames) > 0:
            if metafunc.function.__name__ == "test_unit":
                # Create the test in itself
                if self.unit_tests:
                    metafunc.parametrize(metafunc.fixturenames[0], self.unit_tests,
                                         ids=lambda test_param: (test_param.unit_test.spec_file_name or "") + "@" +
                                         (test_param.test_config.pytest_path or ""))
            else:
                metafunc.parametrize(metafunc.fixturenames[0],
                                     [SpecSkipped(MUST.TestSpec, None, "No triplestore found")],
                                     ids=lambda x: "No configuration found for this test")

    # Generate test for each triple store available
    def generate_tests_for_config(self, config, triple_stores, file_name):

        shacl_graph = Graph().parse(Path(os.path.join(mustrd_root, "model/mustrdShapes.ttl")))
        ont_graph = Graph().parse(Path(os.path.join(mustrd_root, "model/ontology.ttl")))
        valid_spec_uris, spec_graph, invalid_spec_results = validate_specs(config, triple_stores,
                                                                           shacl_graph, ont_graph, file_name or "*")

        specs, skipped_spec_results = \
            get_specs(valid_spec_uris, spec_graph, triple_stores, config)

        # Return normal specs + skipped results
        return specs + skipped_spec_results + invalid_spec_results

    # Function called to generate the name of the test
    def get_test_name(self, spec):
        # FIXME: SpecSkipped should have the same structure?
        if isinstance(spec, SpecSkipped):
            triple_store = spec.triple_store
        else:
            triple_store = spec.triple_store['type']
        triple_store_name = triple_store.replace("https://mustrd.com/model/", "")
        test_name = spec.spec_uri.replace(spnamespace, "").replace("_", " ")
        return triple_store_name + ": " + test_name

    # Get triple store configuration or default
    def get_triple_stores_from_file(self, test_config):
        if test_config.triplestore_spec_path:
            try:
                triple_stores = get_triple_stores(get_triple_store_graph(test_config.triplestore_spec_path,
                                                                         self.secrets))
            except Exception as e:
                print(f"""Triplestore configuration parsing failed {test_config.triplestore_spec_path}.
                    Only rdflib will be executed""", e)
                triple_stores = [{'type': TRIPLESTORE.RdfLib, 'uri': TRIPLESTORE.RdfLib}]
        else:
            print("No triple store configuration required: using embedded rdflib")
            triple_stores = [{'type': TRIPLESTORE.RdfLib, 'uri': TRIPLESTORE.RdfLib}]

        if test_config.filter_on_tripleStore:
            triple_stores = list(filter(lambda triple_store: (triple_store["uri"] in test_config.filter_on_tripleStore),
                                        triple_stores))
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

        if result.when == 'call':
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
                test_name = test_conf.name.replace(class_name, "").replace("[", "").replace("]", "")
                is_mustrd = True
            # Case normal unit tests
            else:
                module_name = test_conf.parent.parent.name
                class_name = test_conf.parent.name
                test_name = test_conf.originalname
                is_mustrd = False

            test_results.append(TestResult(test_name, class_name, module_name, result.outcome, is_mustrd))

        result_list = ResultList(None, get_result_list(test_results,
                                                       lambda result: result.type,
                                                       lambda result: is_mustrd and result.test_name.split("@")[1]),
                                 False)

        md = result_list.render()
        with open(self.md_path, 'w') as file:
            file.write(md)


# Function called in the test to actually run it
def run_test_spec(test_spec):
    if isinstance(test_spec, SpecSkipped):
        pytest.skip(f"Invalid configuration, error : {test_spec.message}")
    result = run_spec(test_spec)

    result_type = type(result)
    if result_type == SpecSkipped:
        # FIXME: Better exception management
        pytest.skip("Unsupported configuration")
    return result_type == SpecPassed
