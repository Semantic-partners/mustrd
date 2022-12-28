from mustrd import Given, When, run_scenario
from rdflib import Graph
from rdflib.compare import isomorphic, graph_diff


class TestMustrd:
    def test_scenario_given_state_when_query_all_then_return_state(self):
        triples = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        test-data:sub test-data:pred test-data:obj .
        """
        state = Graph()
        state.parse(data=triples, format="ttl")
        query = """
        select ?s ?p ?o { ?s ?p ?o }
        """
        expected_graph = Graph()
        expected_result = """
        @prefix sh: <http://www.w3.org/ns/shacl#> .
        @prefix must: <https://semanticpartners.com/mustrd/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        [
        sh:order 1 ;
        must:results [
           must:variable "s" ;
           must:binding test-data:sub ; 
            ] ,
             [
           must:variable "p" ;
           must:binding test-data:pred ; 
            ] ,
            [
           must:variable "o" ;
           must:binding test-data:obj  ; 
            ];
        ] .
        """
        expected_graph.parse(data=expected_result, format='ttl')

        g = Given(state)
        w = When(query)

        t = run_scenario(g, w)
        message = error_message(expected_graph, t.graph)
        assert isomorphic(t.graph, expected_graph), message


def error_message(expected_graph, actual_graph) -> str:
    diff = graph_diff(expected_graph, actual_graph)
    in_expected = diff[1]
    in_actual = diff[2]
    in_expected_not_in_actual = (in_expected - in_actual).serialize(format='ttl')
    in_actual_not_in_expected = (in_actual - in_expected).serialize(format='ttl')
    return f"in_expected_not_in_actual\n{in_expected_not_in_actual}\nin_actual_not_in_expected\n{in_actual_not_in_expected}"
