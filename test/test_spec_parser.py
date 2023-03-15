import pandas

from mustrd import get_spec_component
from rdflib import Graph
from rdflib.compare import isomorphic
from rdflib.namespace import Namespace, XSD
from graph_util import graph_comparison_message
from namespace import MUST

TEST_DATA = Namespace("https://semanticpartners.com/data/test/")


class TestSpecParserTest:
    select_spec_uri = TEST_DATA.a_complete_select_spec
    select_spec = f"""
            @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
            @prefix sh: <http://www.w3.org/ns/shacl#> .
            @prefix must: <https://mustrd.com/model/> .
            @prefix test-data: <https://semanticpartners.com/data/test/> .
            
            
            <{select_spec_uri}>
                 a          must:TestSpec ;
    must:given [ must:dataSource [ a must:StatementsDataSource ;
                                   must:statements [ a rdf:Statement ;
                                                     rdf:subject   test-data:sub ;
                                                     rdf:predicate test-data:pred ;
                                                     rdf:object    test-data:obj ; ] ; ] ; ] ;
    must:when  [ must:dataSource [ a must:textDataSource ;
                                   must:text  "select ?s ?p ?o {{ ?s ?p ?o }}" ; ] ;
                 must:queryType must:SelectSparql   ; ] ;
    must:then  [ must:dataSource [ a must:TableDataSource ;
                                   must:rows [ must:row [
                                        must:variable "s" ;
                                        must:binding  test-data:sub ; ],
                                      [ must:variable "p" ;
                                        must:binding  test-data:pred ; ],
                                      [ must:variable "o" ;
                                        must:binding  test-data:obj ; ] ; ] ;
               ] ; ] .
            """

    construct_spec_uri = TEST_DATA.a_construct_spec
    construct_spec = f"""
            @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
            @prefix must: <https://mustrd.com/model/> .
            @prefix test-data: <https://semanticpartners.com/data/test/> .


            <{construct_spec_uri}>
                a          must:TestSpec ;
    must:given [ must:dataSource [ a must:StatementsDataSource ;
                                   must:statements [ a rdf:Statement ;
                                                     rdf:subject   test-data:sub ;
                                                     rdf:predicate test-data:pred ;
                                                     rdf:object    test-data:obj ; ] ; ] ; ] ;
    must:when  [ must:dataSource [ a must:textDataSource ;
                                   must:text  "construct {{ ?o ?s ?p }} {{ ?s ?p ?o }}" ; ] ;
                 must:queryType must:ConstructSparql  ; ] ;
    must:then  [ must:dataSource [ a must:StatementsDataSource ;
                 must:statements [ a             rdf:Statement ;
                                   rdf:subject   test-data:obj ;
                                   rdf:predicate test-data:sub ;
                                   rdf:object    test-data:pred ; ] ; ] ; ] .
            """

    def test_given(self):
        spec_graph = Graph()
        spec_graph.parse(data=self.select_spec, format='ttl')
        given_component = get_spec_component(subject=self.select_spec_uri,
                                             predicate=MUST.given,
                                             spec_graph=spec_graph)
        given = Graph()
        given.parse(data=given_component.value, format='ttl')

        expected_triples = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        test-data:sub test-data:pred test-data:obj .
        """
        expected_initial_state = Graph()
        expected_initial_state.parse(data=expected_triples, format='ttl')

        assert isomorphic(given, expected_initial_state), graph_comparison_message(expected_initial_state, given)

    def test_when_select(self):
        spec_graph = Graph()
        spec_graph.parse(data=self.select_spec, format='ttl')

        when_component = get_spec_component(subject=self.select_spec_uri,
                                            predicate=MUST.when,
                                            spec_graph=spec_graph)

        expected_query = "select ?s ?p ?o { ?s ?p ?o }"

        assert when_component.value == expected_query

    def test_then_select(self):
        spec_graph = Graph()
        spec_graph.parse(data=self.select_spec, format='ttl')
        then_component = get_spec_component(subject=self.select_spec_uri,
                                            predicate=MUST.then,
                                            spec_graph=spec_graph)

        expected_df = pandas.DataFrame(
            [[str(TEST_DATA.sub), str(XSD.anyURI), str(TEST_DATA.pred), str(XSD.anyURI), str(TEST_DATA.obj), str(XSD.anyURI)]],
            columns=["s", "s_datatype", "p", "p_datatype", "o", "o_datatype"])

        df_diff = expected_df.compare(then_component.value, result_names=("expected", "actual"))
        assert df_diff.empty, f"\n{df_diff.to_markdown()}"

    def test_when_construct(self):
        spec_graph = Graph()
        spec_graph.parse(data=self.construct_spec, format='ttl')
        when_component = get_spec_component(subject=self.construct_spec_uri,
                                            predicate=MUST.when,
                                            spec_graph=spec_graph)

        expected_query = "construct { ?o ?s ?p } { ?s ?p ?o }"

        assert when_component.value == expected_query

    def test_then_construct(self):
        spec_graph = Graph()
        spec_graph.parse(data=self.construct_spec, format='ttl')

        then_component = get_spec_component(subject=self.construct_spec_uri,
                                            predicate=MUST.then,
                                            spec_graph=spec_graph)

        then = Graph()
        then.parse(data=then_component.value, format='ttl')

        expected_graph = Graph()
        expected_graph.add((TEST_DATA.obj, TEST_DATA.sub, TEST_DATA.pred))

        assert isomorphic(then, expected_graph), graph_comparison_message(expected_graph, then)
