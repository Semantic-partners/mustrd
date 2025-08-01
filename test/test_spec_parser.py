"""
MIT License

Copyright (c) 2023 Semantic Partners Ltd

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import pandas

from rdflib import Graph
from rdflib.compare import isomorphic
from rdflib.namespace import Namespace, XSD
from graph_util import graph_comparison_message
from mustrd.namespace import MUST, TRIPLESTORE
from mustrd.spec_component import ThenSpec, GivenSpec, TableThenSpec, parse_spec_component

TEST_DATA = Namespace("https://semanticpartners.com/data/test/")


class TestSpecParserTest:
    triple_store = {"type": TRIPLESTORE.RdfLib}
    select_spec_uri = TEST_DATA.a_complete_select_spec
    select_spec = f"""
            @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
            @prefix sh: <http://www.w3.org/ns/shacl#> .
            @prefix must: <https://mustrd.org/model/> .
            @prefix test-data: <https://semanticpartners.com/data/test/> .

            <{select_spec_uri}>
                 a          must:TestSpec ;
    must:given [ a must:StatementsDataset ;
                                   must:hasStatement [ a rdf:Statement ;
                                                     rdf:subject   test-data:sub ;
                                                     rdf:predicate test-data:pred ;
                                                     rdf:object    test-data:obj ; ] ; ] ;
    must:when  [ a must:TextSparqlSource ;
                                   must:queryText  "select ?s ?p ?o {{ ?s ?p ?o }}" ;
                 must:queryType must:SelectSparql   ; ] ;
    must:then  [ a must:TableDataset ;
                                   must:hasRow [ must:hasBinding[
                                        must:variable "s" ;
                                        must:boundValue  test-data:sub ; ],
                                      [ must:variable "p" ;
                                        must:boundValue  test-data:pred ; ],
                                      [ must:variable "o" ;
                                        must:boundValue  test-data:obj ; ] ;
               ] ; ] .
            """

    construct_spec_uri = TEST_DATA.a_construct_spec
    construct_spec = f"""
            @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
            @prefix must: <https://mustrd.org/model/> .
            @prefix test-data: <https://semanticpartners.com/data/test/> .


            <{construct_spec_uri}>
                a          must:TestSpec ;
    must:given [ a must:StatementsDataset ;
                                   must:hasStatement [ a rdf:Statement ;
                                                     rdf:subject   test-data:sub ;
                                                     rdf:predicate test-data:pred ;
                                                     rdf:object    test-data:obj ; ] ; ] ;
    must:when  [ a must:TextSparqlSource ;
                                   must:queryText  "construct {{ ?o ?s ?p }} {{ ?s ?p ?o }}" ;
                 must:queryType must:ConstructSparql  ; ] ;
    must:then  [ a must:StatementsDataset ;
                 must:hasStatement [ a             rdf:Statement ;
                                   rdf:subject   test-data:obj ;
                                   rdf:predicate test-data:sub ;
                                   rdf:object    test-data:pred ; ] ; ] .
            """

    def test_given(self):
        spec_graph = Graph()
        spec_graph.parse(data=self.select_spec, format='ttl')
        given_component = parse_spec_component(subject=self.select_spec_uri,
                                               predicate=MUST.given,
                                               spec_graph=spec_graph,
                                               run_config=None,
                                               mustrd_triple_store=self.triple_store)

        given = given_component.value

        expected_triples = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        test-data:sub test-data:pred test-data:obj .
        """
        expected_initial_state = Graph()
        expected_initial_state.parse(data=expected_triples, format='ttl')

        assert isinstance(given_component, GivenSpec)
        assert isomorphic(given, expected_initial_state), graph_comparison_message(expected_initial_state, given)

    def test_when_select(self):
        spec_graph = Graph()
        spec_graph.parse(data=self.select_spec, format='ttl')

        when_component = parse_spec_component(subject=self.select_spec_uri,
                                              predicate=MUST.when,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        expected_query = "select ?s ?p ?o { ?s ?p ?o }"

        assert isinstance(when_component, list)
        assert when_component[0].value == expected_query

    def test_then_select(self):
        spec_graph = Graph()
        spec_graph.parse(data=self.select_spec, format='ttl')
        then_component = parse_spec_component(subject=self.select_spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        expected_df = pandas.DataFrame(
            [[str(TEST_DATA.sub), str(XSD.anyURI), str(TEST_DATA.pred), str(XSD.anyURI), str(TEST_DATA.obj),
              str(XSD.anyURI)]],
            columns=["s", "s_datatype", "p", "p_datatype", "o", "o_datatype"])
        actual_result = then_component.value[["s", "s_datatype", "p", "p_datatype", "o", "o_datatype"]]
        df_diff = expected_df.compare(actual_result, result_names=("expected", "actual"))
        assert df_diff.empty, f"\n{df_diff.to_markdown()}"
        assert isinstance(then_component, TableThenSpec)

    def test_when_construct(self):
        spec_graph = Graph()
        spec_graph.parse(data=self.construct_spec, format='ttl')
        when_component = parse_spec_component(subject=self.construct_spec_uri,
                                              predicate=MUST.when,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        expected_query = "construct { ?o ?s ?p } { ?s ?p ?o }"

        assert when_component[0].value == expected_query
        assert isinstance(when_component, list)

    def test_then_construct(self):
        spec_graph = Graph()
        spec_graph.parse(data=self.construct_spec, format='ttl')

        then_component = parse_spec_component(subject=self.construct_spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        then = then_component.value

        expected_graph = Graph()
        expected_graph.add((TEST_DATA.obj, TEST_DATA.sub, TEST_DATA.pred))

        assert isinstance(then_component, ThenSpec)
        assert isomorphic(then, expected_graph), graph_comparison_message(expected_graph, then)
