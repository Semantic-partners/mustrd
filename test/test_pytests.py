# content of test_sysexit.py
import pytest
from pathlib import Path
from rdflib import URIRef, Graph
from rdflib.namespace import Namespace
import os

from mustrd import SpecResult, run_specs, SpecPassed, SpecSkipped, validate_specs, review_results
from namespace import MUST
from src.utils import get_project_root


import os
from typing import List

from rdflib.plugins.parsers.notation3 import BadSyntax


from pathlib import Path
from requests import ConnectionError

from rdflib import Graph, URIRef

from namespace import MUST
from mustrd import get_spec, run_spec, review_results

TEST_DATA = Namespace("https://semanticpartners.com/data/test/")
    
def pytest_generate_tests(metafunc):
    project_root = get_project_root()
    run_config = {"spec_path": project_root / "test" / "test-specs",
                    "data_path": project_root / "test" / "data"}
    shacl_graph = Graph().parse(Path(os.path.join(project_root, "model/mustrdShapes.ttl")))
    ont_graph = Graph().parse(Path(os.path.join(project_root, "model/ontology.ttl")))
    triple_stores = [{'type': MUST.RdfLib}]
    valid_spec_uris, spec_graph, invalid_spec_results = \
        validate_specs(run_config, triple_stores, shacl_graph, ont_graph)
        
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
                        specs += [get_spec(spec_uri, spec_graph, run_config, triple_store)]
                    except (ValueError, FileNotFoundError, ConnectionError) as e:
                        results += [SpecSkipped(spec_uri, triple_store['type'], e)]

    except (BadSyntax, FileNotFoundError) as e:
        template = "An exception of type {0} occurred when trying to parse the triple store configuration file. " \
                   "Arguments:\n{1!r}"
        message = template.format(type(e).__name__, e.args)
        print(message)
        print("No specifications will be run.")

    print(f"Extracted {len(specs)} specifications that will be run")
    # https://github.com/Semantic-partners/mustrd/issues/115

    
    if "spec" in metafunc.fixturenames:
        metafunc.parametrize("spec", specs, ids=get_test_name)
        

def test_all(spec):
    result = run_spec(spec)
    print(review_results([result], False))
    result_type = type(result)
    if(result_type==SpecSkipped):
        pytest.skip("unsupported configuration")
    assert type(result) == SpecPassed

def get_test_name(spec):
    return spec.spec_uri.replace(TEST_DATA, "").replace("_", " ")
    