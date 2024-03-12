from dataclasses import dataclass
import pytest
import os
from pathlib import Path
from rdflib.namespace import Namespace
from rdflib import Graph

from utils import get_project_root
from mustrd import get_triple_stores, SpecSkipped, validate_specs, get_specs
from namespace import MUST
from collections import defaultdict
from pytest import Session
from mustrd import run_spec, SpecPassed, SpecSkipped

spnamespace = Namespace("https://semanticpartners.com/data/test/")

project_root = get_project_root()

# FIXME: this should probably go to a file. What kind of file: toml, ttl? should the file be versionned?
test_config = {
    "test_unit": {
        "spec_path": "test/test-specs",
        "data_path": "test/data",
        "filter_on_tripleStore": [MUST.RdfLib]
    },
    "test_w3c_gdb": {
        "spec_path": "test/triplestore_w3c_compliance",
        "data_path": "test/data",
        "triplestore_spec_path": "test/triplestore_config/tripleStores-template.ttl",
        "filter_on_tripleStore": [MUST.GraphDb]
    },
    "test_w3c_rdflib": {
        "spec_path": "test/triplestore_w3c_compliance",
        "data_path": "test/data",
        "filter_on_tripleStore": [MUST.RdfLib]
    }
}

class MustrdTestPlugin:
    md_path: str
    
    def __init__(self):
        return
    
    # FIXME: use md_path given in parameter
    #def __init__(self,md_path):
    #    self.md_path = md_path

    # Hook called at collection time: reads the configuration of the tests, and generate pytests from it
    def pytest_generate_tests(self, metafunc):
        if metafunc.function.__name__ in test_config and len(metafunc.fixturenames) > 0:
            one_test_config = test_config[metafunc.function.__name__]

            triple_stores = self.get_triple_stores_from_file(one_test_config)

            unit_tests = self.generate_tests_for_config({"spec_path": project_root / one_test_config["spec_path"],
                                                    "data_path": project_root / one_test_config["data_path"]},
                                                triple_stores)

            # If the triple store is not available for some reason, then create a unique fake test, automatically skipped.
            if "filter_on_tripleStore" in one_test_config and not triple_stores:
                unit_tests = []
                for triple_store in one_test_config["filter_on_tripleStore"]:
                    unit_tests += [SpecSkipped(MUST.TestSpec, triple_store, "No triplestore found")]

            # Create the test in itself
            if unit_tests:
                metafunc.parametrize(metafunc.fixturenames[0], unit_tests, ids=self.get_test_name)


    # Generate test for each triple store available
    def generate_tests_for_config(self, config, triple_stores):

        shacl_graph = Graph().parse(Path(os.path.join(project_root, "model/mustrdShapes.ttl")))
        ont_graph = Graph().parse(Path(os.path.join(project_root, "model/ontology.ttl")))
        valid_spec_uris, spec_graph, invalid_spec_results = validate_specs(config, triple_stores, shacl_graph, ont_graph)

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
        if "triplestore_spec_path" in test_config:
            try:
                triple_stores = get_triple_stores(Graph().parse(project_root / test_config["triplestore_spec_path"]))
            except Exception:
                print(f"""No triple store configuration found at {project_root / test_config['triplestore_spec_path']}.
                    Fall back: only embedded rdflib will be executed""")
                triple_stores = [{'type': MUST.RdfLib}]
        else:
            print("No triple store configuration required: using embedded rdflib")
            triple_stores = [{'type': MUST.RdfLib}]

        if "filter_on_tripleStore" in test_config and test_config["filter_on_tripleStore"]:
            triple_stores = list(filter(lambda triple_store: (triple_store["type"] in test_config["filter_on_tripleStore"]),
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
        md = ""
        result_list = []
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

            result_list.append(TestResult(test_name, class_name, module_name, result.outcome, is_mustrd))

        mustrd_result_dict = defaultdict(lambda: defaultdict(list))
        pytest_result_dict = defaultdict(lambda: defaultdict(list))

        # Partition the list: test generated by mustrd on one side, normal pytests on the other
        for testResult in result_list:
            if testResult.is_mustrd:
                mustrd_result_dict[testResult.module_name][testResult.class_name].append(testResult)
            else:
                pytest_result_dict[testResult.module_name][testResult.class_name].append(testResult)

        # TODO: file name from cmd argument
        with open('junit/github_job_summary.md', 'w') as file:
            file.write("")
            md = "<h1>Mustrd tests summary:</h1>"
            count, success_count, fail_count, skipped_count = self.get_global_stats(mustrd_result_dict)
            md += self.get_summary("Tests", count, success_count, fail_count, skipped_count)
            md += self.generate_md(mustrd_result_dict)
            md += "<h1>Pytest summary:</h1>"
            count, success_count, fail_count, skipped_count = self.get_global_stats(pytest_result_dict)
            md += self.get_summary("Tests", count, success_count, fail_count, skipped_count)
            md += self.generate_md(pytest_result_dict)
            file.write(md)


    # Generate md file section
    # FIXME: should probably use a template
    def generate_md(self, result_dict):
        md = ""
        for module_name, result_in_module in result_dict.items():
            count, success_count, fail_count, skipped_count = self.get_module_stats(result_in_module)
            md += f"""<details>
                            <summary>{self.get_summary(module_name, count, success_count, fail_count, skipped_count)}</summary>
                            """
            for class_name, test_results in result_in_module.items():
                count, success_count, fail_count, skipped_count = self.get_stats(test_results)
                md += f"""<ul>
                            <details>
                                <summary>{self.get_summary(class_name, count, success_count, fail_count, skipped_count)}</summary>"""
                table = """<table class="table">
                            <thead>
                                <tr>
                                    <th scope="col">module</th>
                                    <th scope="col">class</th>
                                    <th scope="col">test</th>
                                    <th scope="col">status</th>
                                <tr>
                            </thead>
                            <tbody>"""
                for test_result in test_results:
                    table += f"""<tr>
                                    <td>{test_result.module_name}</td>
                                    <td>{test_result.class_name}</td>
                                    <td>{test_result.test_name}</td>
                                    <td>{test_result.status}</td>
                                </tr>"""
                table += "</tbody></table>"
                md += table
                md += "</details></ul>"
            md += "</details>"
        return md


    # Aggregate statistic at the class level Count of all tests, count of success/ fail / and skip
    def get_stats(self, test_results):
        count = len(test_results)
        success_count = len(list(filter(lambda x: x.status == "passed", test_results)))
        fail_count = len(list(filter(lambda x: x.status == "failed", test_results)))
        skipped_count = len(list(filter(lambda x: x.status == "skipped", test_results)))
        return count, success_count, fail_count, skipped_count


    # Aggregate statistic at the module level
    def get_module_stats(self, result_in_module):
        return self.aggregate_stats(result_in_module, self.get_stats)


    # Aggregate statistic at the top level
    def get_global_stats(self, result_dict):
        return self.aggregate_stats(result_dict, self.get_module_stats)


    def aggregate_stats(self, results, sub_stat_function):
        count, success_count, fail_count, skipped_count = 0, 0, 0, 0
        for test_results in results.values():
            sub_count, sub_success_count, sub_fail_count, sub_skipped_count = sub_stat_function(test_results)
            count += sub_count
            success_count += sub_success_count
            fail_count += sub_fail_count
            skipped_count += sub_skipped_count
        return count, success_count, fail_count, skipped_count


    # Get summury html to be displayed in the result summary md file
    def get_summary(self, item, count, success_count, fail_count, skipped_count):
        return f"{item}:\n <br/> total: {count}, success: {success_count}, fail: {fail_count}, skipped: {skipped_count}\n"

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
