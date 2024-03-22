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
from TestResult import ResultList, TestResult, get_result_list
import pytest
import os
from pathlib import Path
from rdflib.namespace import Namespace
from rdflib import Graph

from utils import get_project_root
from mustrd import get_triple_store_graph, get_triple_stores, SpecSkipped, validate_specs, get_specs, SpecPassed, run_spec
from namespace import MUST
from pytest import Session
from typing import Dict

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
                metafunc.parametrize(metafunc.fixturenames[0],
                                     [SpecSkipped(MUST.TestSpec, None, "No triplestore found")],
                                     ids=lambda x: "No configuration found for this test")

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
                triple_stores = get_triple_stores(get_triple_store_graph(project_root / test_config.triplestore_spec_path))
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
                                                       lambda result: result.module_name,
                                                       lambda result: result.class_name),
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
