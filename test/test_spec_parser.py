import pandas

from mustrd import get_given, get_when, SelectSparqlQuery, get_then_select, get_then_construct, ConstructSparqlQuery
from rdflib import Graph
from rdflib.compare import isomorphic, graph_diff
from rdflib.namespace import Namespace

TEST_DATA = Namespace("https://semanticpartners.com/data/test/")


class TestSpecParserTest:

    select_spec_uri = TEST_DATA.a_complete_select_spec
    select_spec = f"""
            @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
            @prefix sh: <http://www.w3.org/ns/shacl#> .
            @prefix must: <https://semanticpartners.com/mustrd/> .
            @prefix test-data: <https://semanticpartners.com/data/test/> .
            
            
            <{select_spec_uri}>
                a must:TestSpec ;
                must:given [
                    a rdf:Statement ;
                    rdf:subject test-data:sub ;
                    rdf:predicate test-data:pred ;
                    rdf:object test-data:obj ;
                ] ;
                must:when [
                    a must:SelectSparql ;
                    must:query "select ?s ?p ?o {{ ?s ?p ?o }}" ;
                ] ;
                must:then [
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

    def test_given(self):

        spec_graph = Graph()
        spec_graph.parse(data=self.select_spec, format='ttl')
        givens = get_given(self.select_spec_uri, spec_graph)

        expected_triples = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        test-data:sub test-data:pred test-data:obj .
        """
        expected_initial_state = Graph()
        expected_initial_state.parse(data=expected_triples, format='ttl')

        assert isomorphic(givens, expected_initial_state), graph_comparison_message(expected_initial_state, givens)

    def test_when_select(self):
        spec_graph = Graph()
        spec_graph.parse(data=self.select_spec, format='ttl')
        when = get_when(self.select_spec_uri, spec_graph)

        expected_query = SelectSparqlQuery("select ?s ?p ?o { ?s ?p ?o }")

        assert when == expected_query

    def test_then_select(self):
        spec_graph = Graph()
        spec_graph.parse(data=self.select_spec, format='ttl')
        thens = get_then_select(self.select_spec_uri, spec_graph)
        expected_df = pandas.DataFrame([[TEST_DATA.sub, TEST_DATA.pred, TEST_DATA.obj]], columns=["s", "p", "o"])
        df_diff = expected_df.compare(thens, result_names=("expected", "actual"))
        assert df_diff.empty, f"\n{df_diff.to_markdown()}"

    construct_spec_uri = TEST_DATA.a_construct_spec
    construct_spec = f"""
            @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
            @prefix must: <https://semanticpartners.com/mustrd/> .
            @prefix test-data: <https://semanticpartners.com/data/test/> .
            
            
            <{construct_spec_uri}>
                a must:TestSpec ;
                must:given [
                    a rdf:Statement ;
                    rdf:subject test-data:sub ;
                    rdf:predicate test-data:pred ;
                    rdf:object test-data:obj ;
                ] ;
                must:when [
                    a must:ConstructSparql ;
                    must:query "construct {{ ?o ?s ?p }} {{ ?s ?p ?o }}" ;
                ] ;
                must:then [
                    a rdf:Statement ;
                    rdf:subject test-data:obj ;
                    rdf:predicate test-data:sub ;
                    rdf:object test-data:pred ;
                ] .
            """

    def test_when_construct(self):
        spec_graph = Graph()
        spec_graph.parse(data=self.construct_spec, format='ttl')
        when = get_when(self.construct_spec_uri, spec_graph)

        expected_query = ConstructSparqlQuery(f"construct {{ ?o ?s ?p }} {{ ?s ?p ?o }}")

        assert when == expected_query

    def test_then_construct(self):
        spec_graph = Graph()
        spec_graph.parse(data=self.construct_spec, format='ttl')
        then = get_then_construct(self.construct_spec_uri, spec_graph)

        expected_graph = Graph()
        expected_graph.add((TEST_DATA.obj, TEST_DATA.sub, TEST_DATA.pred))

        assert isomorphic(then, expected_graph), graph_comparison_message(expected_graph, then)


def graph_comparison_message(expected_graph, actual_graph) -> str:
    diff = graph_diff(expected_graph, actual_graph)
    in_expected = diff[1]
    in_actual = diff[2]
    in_expected_not_in_actual = (in_expected - in_actual).serialize(format='ttl')
    in_actual_not_in_expected = (in_actual - in_expected).serialize(format='ttl')
    in_both = diff[0].serialize(format='ttl')
    message = f"\nin_expected_not_in_actual\n{in_expected_not_in_actual}\nin_actual_not_in_expected\n{in_actual_not_in_expected}\nin_both\n{in_both}"
    return message

