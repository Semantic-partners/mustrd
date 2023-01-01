import pandas

from mustrd import get_given, get_when, SelectSparqlQuery, get_then_select, get_then_construct, ConstructSparqlQuery
from rdflib import Graph
from rdflib.compare import isomorphic
from rdflib.namespace import Namespace, XSD
from graph_util import graph_comparison_message

TEST_DATA = Namespace("https://semanticpartners.com/data/test/")


class TestSpecParserTest:

    select_spec_uri = TEST_DATA.a_complete_select_spec
    select_spec = f"""
            @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
            @prefix sh: <http://www.w3.org/ns/shacl#> .
            @prefix must: <https://mustrd.com/model/> .
            @prefix test-data: <https://semanticpartners.com/data/test/> .
            
            
            <{select_spec_uri}>
                a must:TestSpec ;
                must:given [ a must:StatementsDataset ;
                             must:statements [
                                a rdf:Statement ;
                                rdf:subject test-data:sub ;
                                rdf:predicate test-data:pred ;
                                rdf:object test-data:obj ;
                             ] ; 
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
        expected_df = pandas.DataFrame([[TEST_DATA.sub, XSD.anyURI, TEST_DATA.pred, XSD.anyURI, TEST_DATA.obj, XSD.anyURI]], columns=["s", "s_datatype", "p", "p_datatype", "o", "o_datatype"])
        df_diff = expected_df.compare(thens, result_names=("expected", "actual"))
        assert df_diff.empty, f"\n{df_diff.to_markdown()}"

    construct_spec_uri = TEST_DATA.a_construct_spec
    construct_spec = f"""
            @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
            @prefix must: <https://mustrd.com/model/> .
            @prefix test-data: <https://semanticpartners.com/data/test/> .
            
            
            <{construct_spec_uri}>
                a must:TestSpec ;
                must:given [a must:StatementsDataset ;
                            must:statements [
                                a rdf:Statement ;
                                rdf:subject test-data:sub ;
                                rdf:predicate test-data:pred ;
                                rdf:object test-data:obj ;
                            ] ; ] ;
                must:when [
                    a must:ConstructSparql ;
                    must:query "construct {{ ?o ?s ?p }} {{ ?s ?p ?o }}" ;
                ] ;
                must:then [a must:StatementsDataset ;
                           must:statements [
                                a rdf:Statement ;
                                rdf:subject test-data:obj ;
                                rdf:predicate test-data:sub ;
                                rdf:object test-data:pred ;
                            ] ; ] .
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

