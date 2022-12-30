from rdflib import Graph
from rdflib.namespace import Namespace
from rdflib.compare import isomorphic

from mustrd import SpecPassed, run_construct_spec, get_then_construct, ConstructSparqlQuery, ConstructSpecFailure
from graph_util import graph_comparison_message

TEST_DATA = Namespace("https://semanticpartners.com/data/test/")


class TestRunConstructSpec:
    def test_construct_spec_passes(self):
        triples = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        test-data:sub test-data:pred test-data:obj .
        """

        state = Graph()
        state.parse(data=triples, format="ttl")
        construct_query = """
        construct { ?o ?s ?p } { ?s ?p ?o }
        """
        spec_graph = Graph()
        spec = """
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
        
        test-data:my_first_spec 
            a must:TestSpec ;
            must:then [
                    a rdf:Statement ;
                    rdf:subject test-data:obj ;
                    rdf:predicate test-data:sub ;
                    rdf:object test-data:pred ;
                ] .
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_first_spec

        then_df = get_then_construct(spec_uri, spec_graph)
        t = run_construct_spec(spec_uri, state, ConstructSparqlQuery(construct_query), then_df)

        expected_result = SpecPassed(spec_uri)
        assert t == expected_result

    def test_construct_spec_fails_with_graph_comparison(self):
        triples = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        test-data:sub test-data:pred test-data:obj .
        """

        state = Graph()
        state.parse(data=triples, format="ttl")
        construct_query = """
        construct { ?p ?o ?s } { ?s ?p ?o }
        """
        spec_graph = Graph()
        spec = """
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
        
        test-data:my_failing_construct_spec 
            a must:TestSpec ;
            must:then [
                    a rdf:Statement ;
                    rdf:subject test-data:obj ;
                    rdf:predicate test-data:sub ;
                    rdf:object test-data:pred ;
                ] .
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_construct_spec

        then_df = get_then_construct(spec_uri, spec_graph)
        result = run_construct_spec(spec_uri, state, ConstructSparqlQuery(construct_query), then_df)

        assert result.spec_uri == spec_uri

        expected_in_expected_not_in_actual = Graph()
        expected_in_expected_not_in_actual.add((TEST_DATA.obj, TEST_DATA.sub, TEST_DATA.pred))

        expected_in_actual_not_in_expected = Graph()
        expected_in_actual_not_in_expected.add((TEST_DATA.pred, TEST_DATA.obj, TEST_DATA.sub))

        result_type = type(result)
        if result_type == ConstructSpecFailure:
            graph_comparison = result.graph_comparison
            assert isomorphic(graph_comparison.in_expected_not_in_actual, expected_in_expected_not_in_actual), graph_comparison_message(expected_in_expected_not_in_actual, graph_comparison.in_expected_not_in_actual)
            assert isomorphic(graph_comparison.in_actual_not_in_expected, expected_in_actual_not_in_expected), graph_comparison_message(expected_in_actual_not_in_expected, graph_comparison.in_actual_not_in_expected)
            assert len(graph_comparison.in_both.all_nodes()) == 0
        else:
            raise Exception(f"Unexpected result type {result_type}")
