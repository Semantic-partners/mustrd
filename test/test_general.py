import unittest
import os
from pathlib import Path

from mustrd.mustrd import run_specs, get_triple_stores, validate_specs, get_specs
from rdflib import Graph
from mustrd.namespace import TRIPLESTORE
from mustrd.utils import get_mustrd_root


class RunGeneralTests(unittest.TestCase):
    def setUp(self):
        # Set up any necessary resources or dependencies for the tests
        self.invalid_triple_store_configuration = "invalid_path"

        current_dir = Path(__file__).resolve().parent
        self.spec_path = current_dir / "test_folder"
        os.makedirs(self.spec_path, exist_ok=True)

        self.invalid_spec_path = current_dir / "invalid_folder"

        # Create the test TTL file
        self.test_ttl_file = self.spec_path / "test_file.ttl"
        ttl_content = '''@prefix must:      <https://mustrd.com/model/> .
@prefix test-data: <https://semanticpartners.com/data/test/> .
@prefix rdf:       <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

test-data:a_complete_construct_scenario
    a          must:TestSpec ;
    must:given [ a must:StatementsDataset ;
                                   must:hasStatement [ a rdf:Statement ;
                                                     rdf:subject   test-data:sub ;
                                                     rdf:predicate test-data:pred ;
                                                     rdf:object    test-data:obj ; ] ; ] ;
    must:when  [ a must:TextSparqlSource ;
                 must:queryText  "construct { ?o ?s ?p } where { ?s ?p ?o }" ;
                 must:queryType must:ConstructSparql  ; ] ;
    must:then  [ a must:StatementsDataset ;
                 must:hasStatement [ a             rdf:Statement ;
                                   rdf:subject   test-data:obj ;
                                   rdf:predicate test-data:sub ;
                                   rdf:object    test-data:pred ; ] ; ]  .
'''

        with open(self.test_ttl_file, "w") as file:
            file.write(ttl_content)

    def tearDown(self):
        # Clean up the temporary folder and files after the tests
        os.remove(self.test_ttl_file)
        os.rmdir(self.spec_path)

    def test_run_specs_with_invalid_triplestore_config(self):
        # Call the function with the specified parameters
        results = get_triple_stores(Graph())
        # Perform assertions or checks on the results if needed
        self.assertIsInstance(results, list)
        self.assertEqual(len(results), 0)  # Assert that no results were returned

    def test_run_specs_with_invalid_spec_path(self):
        # Define an invalid spec_path
        triple_stores = [{'type': TRIPLESTORE.RdfLib}]
        run_config = {'spec_path': Path("not_exists")}
        shacl_graph = Graph().parse(Path(os.path.join(get_mustrd_root(), "model/mustrdShapes.ttl")))
        ont_graph = Graph().parse(Path(os.path.join(get_mustrd_root(), "model/ontology.ttl")))

        valid_spec_uris, spec_graph, invalid_spec_results = \
            validate_specs(run_config, triple_stores, shacl_graph, ont_graph)

        specs, skipped_spec_results = \
            get_specs(valid_spec_uris, spec_graph, triple_stores, run_config)
            
        final_results = invalid_spec_results + skipped_spec_results + run_specs(specs)
        # Perform assertions or checks on the results if needed
        self.assertIsInstance(final_results, list)
        self.assertEqual(len(final_results), 0)  # Assert that no results were returned


if __name__ == '__main__':
    unittest.main()
