from dataclasses import dataclass
import pytest
import os
from pathlib import Path
from rdflib.namespace import Namespace
from rdflib import Graph

from utils import get_project_root
from mustrd import get_triple_stores, SpecSkipped, validate_specs, get_specs, SpecPassed, run_spec
from namespace import MUST
from pytest import Session
from typing import Dict, Union
from itertools import groupby
from jinja2 import Environment, FileSystemLoader

spnamespace = Namespace("https://semanticpartners.com/data/test/")

project_root = get_project_root()


@dataclass
class TestConfig:
    test_function: str
    spec_path: str
    data_path: str
    triplestore_spec_path: str
    filter_on_tripleStore: str

    def __init__(self, test_function: str, spec_path: str, data_path: str, triplestore_spec_path: str,
                 filter_on_tripleStore: str = None):
        self.test_function = test_function
        self.spec_path = spec_path
        self.data_path = data_path
        self.triplestore_spec_path = triplestore_spec_path
        self.filter_on_tripleStore = filter_on_tripleStore


class MustrdTestPlugin:
    md_path: str
    test_configs: Dict[str, TestConfig]

    def __init__(self, md_path, test_configs):
        self.md_path = md_path
        self.test_configs = test_configs

    # Hook called at collection time: reads the configuration of the tests, and generate pytests from it
    def pytest_generate_tests(self, metafunc):

        if len(metafunc.fixturenames) > 0:
            if metafunc.function.__name__ in self.test_configs:
                one_test_config = self.test_configs[metafunc.function.__name__]

                triple_stores = self.get_triple_stores_from_file(one_test_config)

                unit_tests = []
                if one_test_config.filter_on_tripleStore and not triple_stores:
                    unit_tests = list(map(lambda triple_store:
                                      SpecSkipped(MUST.TestSpec, triple_store, "No triplestore found"),
                                      one_test_config.filter_on_tripleStore))
                else:
                    unit_tests = self.generate_tests_for_config({"spec_path": project_root / one_test_config.spec_path,
                                                                "data_path": project_root / one_test_config.data_path},
                                                                triple_stores)

                # Create the test in itself
                if unit_tests:
                    metafunc.parametrize(metafunc.fixturenames[0], unit_tests, ids=self.get_test_name)
            else:
                metafunc.parametrize(metafunc.fixturenames[0], [SpecSkipped(MUST.TestSpec, None, "No triplestore found")], ids=lambda x: "No configuration found for this test")

    # Generate test for each triple store available
    def generate_tests_for_config(self, config, triple_stores):

        shacl_graph = Graph().parse(Path(os.path.join(project_root, "model/mustrdShapes.ttl")))
        ont_graph = Graph().parse(Path(os.path.join(project_root, "model/ontology.ttl")))
        valid_spec_uris, spec_graph, invalid_spec_results = validate_specs(config, triple_stores,
                                                                           shacl_graph, ont_graph)

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
                triple_stores = get_triple_stores(Graph().parse(project_root / test_config.triplestore_spec_path))
            except Exception:
                print(f"""No triple store configuration found at {project_root / test_config.triplestore_spec_path}.
                    Fall back: only embedded rdflib will be executed""")
                triple_stores = [{'type': MUST.RdfLib}]
        else:
            print("No triple store configuration required: using embedded rdflib")
            triple_stores = [{'type': MUST.RdfLib}]

        if test_config.filter_on_tripleStore:
            triple_stores = list(filter(lambda triple_store: (triple_store["type"] in test_config.filter_on_tripleStore),
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
        md = ""
        test_results = []
        for test_conf, result in session.results.items():
            # Case auto generated tests
            if test_conf.originalname != test_conf.name:
                class_name = test_conf.originalname
                test_name = test_conf.name.replace(class_name, "").replace("[", "").replace("]", "")
                module_name = test_conf.parent.name
                is_mustrd = True
            # Case normal unit tests
            else:
                test_name = test_conf.originalname
                class_name = test_conf.parent.name
                module_name = test_conf.parent.parent.name
                is_mustrd = False

            test_results.append(TestResult(test_name, class_name, module_name, result.outcome, is_mustrd))
        
        result_list = ResultList("Total", get_result_list(test_results,
                                                          lambda result: result.is_mustrd,
                                                          lambda result: result.module_name,
                                                          lambda result: result.class_name),
                                 False)
        
        environment = Environment(loader=FileSystemLoader("src/templates/"))
        md = environment.get_template("md_template.jinja").render(result_list = result_list)
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
    

@dataclass
class TestResult:
    test_name: str
    class_name: str
    module_name: str
    status: str
    is_mustrd: bool

    def __init__(self, test_name: str, class_name: str, module_name: str, status: str, is_mustrd: bool):
        self.test_name = test_name
        self.class_name = class_name
        self.module_name = module_name
        self.status = status
        self.is_mustrd = is_mustrd
        
@dataclass
class Stats:
    count: int
    success_count: int
    fail_count: int
    skipped_count: int
    
    def __init__(self, count: int, success_count: int, fail_count: int, skipped_count: int):
        self.count = count
        self.success_count = success_count
        self.fail_count = fail_count
        self.skipped_count = skipped_count
        
def get_result_list(test_results: list[TestResult], *group_functions):
    if len(group_functions) > 0:
        return list(map(lambda key_value:
                        ResultList(key_value[0], get_result_list(key_value[1], *group_functions[1:]), len(group_functions) == 1),
                        groupby(sorted(test_results, key=group_functions[0]), group_functions[0])))
    else:
        return list(test_results)
    
        

@dataclass
class ResultList:
    name: str
    stats:Stats
    is_leaf: bool
    result_list: Union[list['ResultList'], list[TestResult]] # string type to workaround recursive call
    
    def __init__(self, name: str, result_list: Union[list['ResultList'], list[TestResult]], is_leaf: bool = False):
        self.name = name
        self.result_list = result_list
        self.is_leaf = is_leaf
        self.compute_stats()
    
    def compute_stats(self):
        count, success_count, fail_count, skipped_count = 0, 0, 0, 0
        
        if self.is_leaf:
            count = len(self.result_list)
            success_count = len(list(filter(lambda x: x.status == "passed", self.result_list)))
            fail_count = len(list(filter(lambda x: x.status == "failed", self.result_list)))
            skipped_count = len(list(filter(lambda x: x.status == "skipped", self.result_list)))
        else:
            for test_results in self.result_list:
                sub_count, sub_success_count, sub_fail_count, sub_skipped_count = test_results.compute_stats()
                count += sub_count
                success_count += sub_success_count
                fail_count += sub_fail_count
                skipped_count += sub_skipped_count
        
        self.stats = Stats(count, success_count, fail_count, skipped_count)
        return count, success_count, fail_count, skipped_count
