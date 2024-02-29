# content of test_sysexit.py
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

spnamespace = Namespace("https://semanticpartners.com/data/test/")

project_root = get_project_root()
    
test_data = {
    "test_unit": {
        "fixture" : "unit_tests",
        "spec_path": "test/test-specs",
        "data_path" : "test/data",
        "triplestore_spec_path": "test/triplestore_config/tripleStores-template.ttl",
        "filter_on_tripleStore" : [MUST.RdfLib]
    },    
    "test_w3c_gdb": {
        "fixture" : "w3c_tests",
        "spec_path": "test/triplestore_w3c_compliance",
        "data_path" : "test/data",
        "triplestore_spec_path": "test/triplestore_config/tripleStores-template.ttl",
        "filter_on_tripleStore" : [MUST.GraphDb]
    },    
    "test_w3c_rdflib": {
        "fixture" : "w3c_tests",
        "spec_path": "test/triplestore_w3c_compliance",
        "data_path" : "test/data",
        "triplestore_spec_path": "test/triplestore_config/tripleStores-template.ttl",
        "filter_on_tripleStore" : [MUST.RdfLib]
    }
}

def run_test_spec(test_spec):
    result = run_spec(test_spec)
    print(review_results([result], False))
    result_type = type(result)
    if(result_type==SpecSkipped):
        pytest.skip("unsupported configuration")
    return result_type == SpecPassed

def pytest_generate_tests(metafunc):
    if metafunc.function.__name__ in test_data:
        one_test_data = test_data[metafunc.function.__name__]
        triple_stores = get_triple_stores(Graph().parse(project_root / one_test_data["triplestore_spec_path"]))
        if "filter_on_tripleStore" in one_test_data and one_test_data["filter_on_tripleStore"]:
            triple_stores = list(filter(lambda triple_store: (triple_store["type"] in  one_test_data["filter_on_tripleStore"]), triple_stores)) 
        
        
        unit_tests = generate_tests_for_config({"spec_path": project_root / one_test_data["spec_path"],
                            "data_path": project_root / one_test_data["data_path"]}, triple_stores)
            
        if one_test_data["fixture"] in metafunc.fixturenames and unit_tests:
            metafunc.parametrize(one_test_data["fixture"] , unit_tests, ids=get_test_name)

def generate_tests_for_config(config, triple_stores):
    
    shacl_graph = Graph().parse(Path(os.path.join(project_root, "model/mustrdShapes.ttl")))
    ont_graph = Graph().parse(Path(os.path.join(project_root, "model/ontology.ttl")))
    valid_spec_uris, spec_graph, invalid_spec_results = \
    validate_specs(config, triple_stores, shacl_graph, ont_graph)
    specs = []
    try:
        for triple_store in triple_stores:
            if "error" in triple_store:
                print(f"{triple_store['error']}. No specs run for this triple store.")
                results += [SpecSkipped(spec_uri, triple_store['type'], triple_store['error']) for spec_uri in
                            invalid_spec_results]
            else:
                for spec_uri in valid_spec_uris:
                    try:
                        specs += [get_spec(spec_uri, spec_graph, config, triple_store)]
                    except (ValueError, FileNotFoundError, ConnectionError) as e:
                        results += [SpecSkipped(spec_uri, triple_store['type'], e)]

    except (BadSyntax, FileNotFoundError) as e:
        template = "An exception of type {0} occurred when trying to parse the triple store configuration file. " \
                "Arguments:\n{1!r}"
        message = template.format(type(e).__name__, e.args)
        print(message)
        print("No specifications will be run.")

    print(f"Extracted {len(specs)} specifications that will be run")
    return specs


def get_test_name(spec):
    return spec.triple_store["type"].replace("https://mustrd.com/model/", "") + ": " + spec.spec_uri.replace(spnamespace, "").replace("_", " ")
    