from mustrd import Given, When, run_test
from rdflib import Graph
from rdflib.compare import isomorphic, graph_diff


class TestMustrd:
    def test_scenario_given_state_when_query_all_then_return_state(self):
        triples = """
        @prefix mustrd: <https://semanticpartners.com/mustrd/> .
        mustrd:sub mustrd:pred mustrd:obj .
        """
        state = Graph()
        state.parse(data=triples, format="ttl")
        query = """
        select ?s ?p ?o { ?s ?p ?o }
        """
        expected_graph = Graph()
        expected_select_triples = """
        @prefix sh: <http://www.w3.org/ns/shacl#> .
        @prefix mustrd: <https://semanticpartners.com/mustrd/> .
        [
        sh:order 1 ;
        mustrd:results [
           mustrd:variable "s" ;
           mustrd:binding mustrd:sub ; 
            ] ,
             [
           mustrd:variable "p" ;
           mustrd:binding mustrd:pred ; 
            ] ,
            [
           mustrd:variable "o" ;
           mustrd:binding mustrd:obj  ; 
            ];
        ] .
        """
        expected_graph.parse(data=expected_select_triples, format='ttl')

        g = Given(state)
        w = When(query)

        t = run_test(g, w)
        message = error_message(expected_graph, t.graph)
        assert isomorphic(t.graph, expected_graph), message


def error_message(expected_graph, actual_graph) -> str:
    diff = graph_diff(expected_graph, actual_graph)
    in_expected = diff[1]
    in_actual = diff[2]
    in_expected_not_in_actual = (in_expected - in_actual).serialize(format='ttl')
    in_actual_not_in_expected = (in_actual - in_expected).serialize(format='ttl')
    return f"in_expected_not_in_actual\n{in_expected_not_in_actual}\nin_actual_not_in_expected\n{in_actual_not_in_expected}"
