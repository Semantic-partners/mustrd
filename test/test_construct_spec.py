from rdflib import Graph
from rdflib.namespace import Namespace

from mustrd import ScenarioResult, run_construct_spec, get_then_construct, ConstructSparqlQuery

TEST_DATA = Namespace("https://semanticpartners.com/data/test/")


class TestRunConstructSpec:
    def test_construct_scenario_passes(self):
        triples = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        test-data:sub test-data:pred test-data:obj .
        """

        state = Graph()
        state.parse(data=triples, format="ttl")
        construct_query = """
        construct { ?o ?s ?p } { ?s ?p ?o }
        """
        scenario_graph = Graph()
        scenario = """
        @prefix must: <https://semanticpartners.com/mustrd/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
        
        test-data:my_first_scenario 
            a must:TestSpec ;
            must:then [
                    a rdf:Statement ;
                    rdf:subject test-data:obj ;
                    rdf:predicate test-data:sub ;
                    rdf:object test-data:pred ;
                ] .
        """
        scenario_graph.parse(data=scenario, format='ttl')

        spec_uri = TEST_DATA.my_first_scenario

        then_df = get_then_construct(spec_uri, scenario_graph)
        t = run_construct_spec(spec_uri, state, ConstructSparqlQuery(construct_query), then_df)

        expected_result = ScenarioResult(spec_uri)
        assert t == expected_result
