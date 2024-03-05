# content of test_sysexit.py
from dataclasses import dataclass
import pytest
import os
from pathlib import Path
from rdflib.namespace import Namespace
from rdflib.plugins.parsers.notation3 import BadSyntax
from rdflib import Graph
from requests import ConnectionError

from src.utils import get_project_root
from mustrd import get_spec, run_spec, review_results, get_triple_stores,SpecPassed, SpecSkipped,validate_specs
from namespace import MUST
from collections import defaultdict
import re
from pytest import Session

spnamespace = Namespace("https://semanticpartners.com/data/test/")

project_root = get_project_root()
    
test_config = {
    "test_unit": {
        "spec_path": "test/test-specs",
        "data_path" : "test/data",
        "filter_on_tripleStore" : [MUST.RdfLib]
    },    
    "test_w3c_gdb": {
        "spec_path": "test/triplestore_w3c_compliance",
        "data_path" : "test/data",
        "triplestore_spec_path": "test/triplestore_config/tripleStores-template.ttl",
        "filter_on_tripleStore" : [MUST.GraphDb]
    },    
    "test_w3c_rdflib": {
        "spec_path": "test/triplestore_w3c_compliance",
        "data_path" : "test/data",
        "filter_on_tripleStore" : [MUST.RdfLib]
    }
}

def run_test_spec(test_spec):
    if type(test_spec)==SpecSkipped:
      pytest.skip(f"Invalid configuration, error : {test_spec.message}")  
    result = run_spec(test_spec)
    print(review_results([result], False))
    result_type = type(result)
    if result_type==SpecSkipped:
        pytest.skip("Unsupported configuration")
    return result_type == SpecPassed

def pytest_generate_tests(metafunc):
    if metafunc.function.__name__ in test_config and len(metafunc.fixturenames) > 0:
        one_test_config = test_config[metafunc.function.__name__]

        triple_stores = get_triple_stores_from_file(one_test_config)
        
        unit_tests = generate_tests_for_config({"spec_path": project_root / one_test_config["spec_path"],
                            "data_path": project_root / one_test_config["data_path"]}, triple_stores)
        if "filter_on_tripleStore" in one_test_config and not triple_stores:
            unit_tests = []
            for triple_store in one_test_config["filter_on_tripleStore"]:
                unit_tests += [SpecSkipped(MUST.TestSpec, triple_store, "No triplestore found")]
        
        if unit_tests:
            metafunc.parametrize(metafunc.fixturenames[0] , unit_tests, ids=get_test_name)

def generate_tests_for_config(config, triple_stores):
    
    shacl_graph = Graph().parse(Path(os.path.join(project_root, "model/mustrdShapes.ttl")))
    ont_graph = Graph().parse(Path(os.path.join(project_root, "model/ontology.ttl")))
    valid_spec_uris, spec_graph, invalid_spec_results = \
    validate_specs(config, triple_stores, shacl_graph, ont_graph)
    specs = invalid_spec_results
    try:
        for triple_store in triple_stores:
            for spec_uri in valid_spec_uris:
                try:
                    specs += [get_spec(spec_uri, spec_graph, config, triple_store)]
                except (ValueError, FileNotFoundError, ConnectionError) as e:
                    specs += [SpecSkipped(spec_uri, triple_store['type'], e)]

    except (BadSyntax, FileNotFoundError) as e:
        template = "An exception of type {0} occurred when trying to parse the triple store configuration file. " \
                "Arguments:\n{1!r}"
        message = template.format(type(e).__name__, e.args)
        print(message)
        print("No specifications will be run.")

    print(f"Extracted {len(specs)} specifications that will be run")
    return specs


def get_test_name(spec):
    # FIXME: SpecSkipped should have the same structure?
    if type(spec) == SpecSkipped:
        triple_store = spec.triple_store
    else:
        triple_store = spec.triple_store['type']
    triple_store_name = triple_store.replace("https://mustrd.com/model/", "")
    test_name = spec.spec_uri.replace(spnamespace, "").replace("_", " ")
    return triple_store_name + ": " + test_name
    
def get_triple_stores_from_file(test_config):
    if "triplestore_spec_path" in test_config:
        try:
            triple_stores = get_triple_stores(Graph().parse(project_root / test_config["triplestore_spec_path"]))
        except Exception as e :
            print(f"No triple store configuration found at {project_root / test_config['triplestore_spec_path']}. Fall back: only embedded rdflib will be executed")
            triple_stores = [{'type': MUST.RdfLib}]
    else :
        print("No triple store configuration required: using embedded rdflib")
        triple_stores = [{'type': MUST.RdfLib}]
        
    if "filter_on_tripleStore" in test_config and test_config["filter_on_tripleStore"]:
        triple_stores = list(filter(lambda triple_store: (triple_store["type"] in  test_config["filter_on_tripleStore"]), triple_stores)) 
    return triple_stores

def pytest_sessionstart(session):
    session.results = dict()


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    result = outcome.get_result()

    if result.when == 'call':
        item.session.results[item] = result

def pytest_sessionfinish(session: Session, exitstatus):
    md = ""
    result_list = []
    for result in session.results.values():   
        test_name = get_match(r'\[(.*?)\]', result.nodeid) or result.nodeid.split("::") [2]
        class_name = get_match(r'::(.*?)\[', result.nodeid) or get_match(r'::(.*?)::', result.nodeid)
        module_name = get_match(r'\/(.*?)\.py', result.nodeid)
        result_list.append(TestResult(test_name, class_name, module_name, result.outcome ))
    
    result_dict = defaultdict(lambda: defaultdict(list))

    # Partition the list
    for testResult in result_list:
        result_dict[testResult.module_name][testResult.class_name].append(testResult)

    result_dict = dict(result_dict)
    
    md = """
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.0.2/dist/css/bootstrap.min.css" rel="stylesheet" integrity="sha384-EVSTQN3/azprG1Anm3QDgpJLIm9Nao0Yz1ztcQTwFspd3yD65VohhpuuCOmLASjC" crossorigin="anonymous">
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.0.2/dist/js/bootstrap.bundle.min.js" integrity="sha384-MrcW6ZMFYlzcLA8Nl+NtUVF0sA7MsXsP1UyJoMp4YLEuNSfAP+JcXn/tWtIaxVXM" crossorigin="anonymous"></script>
<script src="https://ajax.googleapis.com/ajax/libs/jquery/3.7.1/jquery.min.js"></script>
    """
    with open('junit/results.html', 'w') as file:
        file.write(md)
        for module_name, result_in_module in result_dict.items():
            md+=f"""<h1>{module_name}</h1>\n<a class="btn btn-primary" onclick= "$('#module-{module_name}').show();"> See module module-{module_name} results  </a>\n <div id="module-{module_name}" style = "display: none">\n"""
            for class_name, test_results in result_in_module.items():
                count, success_count, fail_count, skipped_count = get_class_stats(test_results)
                md+=f"<h2>{class_name}:</h2>\n <br/> total: {count}, success: {success_count}, fail: {fail_count}, skipped: {skipped_count}<br/>\n"
                md+=f"""<a class="btn btn-primary" onclick= "$('#class-{module_name}-{class_name}').show();">See class class-{module_name}-{class_name}</a> \n <div id="class-{module_name}-{class_name}" style = "display: none">\n"""
                md+= f"""<table class="table">\n<thead>\n<tr>\n<th scope="col">module</th>\n<th scope="col">class</th>\n<th scope="col">test</th>\n<th scope="col">status</th>\n<tr>\n</thead>\n<tbody>\n"""
                for test_result in test_results:
                    md+=f"<tr><td>{test_result.module_name}</td>\n<td>{test_result.class_name}</td>\n<td>{test_result.test_name}</td>\n<td>{test_result.status}</td>\n</tr>\n"
                md+=f"</tbody>\n</table>\n</div>\n"
            md+="</div>"
        file.write(md)
        
    
    print(result_dict)

def get_match(regex, string):
    search = re.search(regex, string)
    if search:
        return search.group(1)
    else: 
        return None
    
   
def get_class_stats(test_results):
    count = len(test_results)
    success_count = len(list(filter(lambda x: x.status == "passed", test_results)))
    fail_count = len(list(filter(lambda x: x.status == "failed", test_results)))
    skipped_count = len(list(filter(lambda x: x.status == "skipped", test_results)))
    return count, success_count, fail_count, skipped_count
     
#def get_module_stats(result_in_module):
#    class_count = result_in_module.keys().count()
#    test_success_count = 
        
@dataclass
class TestResult:
    test_name: str
    class_name: str
    module_name: str
    status: str
    
    def __init__(self, test_name: str, class_name: str, module_name: str, status: str):
        self.test_name = test_name
        self.class_name = class_name
        self.module_name = module_name
        self.status = status