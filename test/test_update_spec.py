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

from rdflib import Graph, Variable, Literal, URIRef
from rdflib.namespace import Namespace
from rdflib.compare import isomorphic

from mustrd import SpecPassed, run_update_spec, UpdateSpecFailure, SparqlParseFailure
from graph_util import graph_comparison_message
from namespace import MUST
from spec_component import parse_spec_component

TEST_DATA = Namespace("https://semanticpartners.com/data/test/")


class TestRunUpdateSpec:
    given_sub_pred_obj = """
    @prefix test-data: <https://semanticpartners.com/data/test/> .
    test-data:sub test-data:pred test-data:obj .
    """

    triple_store = {"type": MUST.RdfLib}

    def test_insert_spec_passes(self):
        state = Graph()
        state.parse(data=self.given_sub_pred_obj, format="ttl")
        insert_query = """
        insert { ?o ?p ?s } where {?s ?p ?o}
        """
        spec_graph = Graph()
        spec = """
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
        
        test-data:my_first_spec 
            a must:TestSpec ;
            must:then  [ a must:StatementsDataSource ;
                 must:statements [ a             rdf:Statement ;
                                   rdf:subject   test-data:sub ;
                                   rdf:predicate test-data:pred ;
                                   rdf:object    test-data:obj ; ] ,
                                 [ a             rdf:Statement ;
                                   rdf:subject   test-data:obj ;
                                   rdf:predicate test-data:pred ;
                                   rdf:object    test-data:sub ; ] ; ] .
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_first_spec

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              folder_location=None,
                                              mustrd_triple_store=self.triple_store)

        t = run_update_spec(spec_uri, state, insert_query, then_component.value, self.triple_store)

        expected_result = SpecPassed(spec_uri, self.triple_store["type"])
        assert t == expected_result

    def test_delete_spec_passes(self):
        state = Graph()
        state.parse(data=self.given_sub_pred_obj, format="ttl")
        delete_query = """
        delete { ?s ?p ?o } where {?s ?p ?o}
        """
        spec_graph = Graph()
        spec = """
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

        test-data:my_first_spec 
            a must:TestSpec ;
                  must:then  [ a must:EmptyGraphResult ] .
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_first_spec

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              folder_location=None,
                                              mustrd_triple_store=self.triple_store)

        t = run_update_spec(spec_uri, state, delete_query, then_component.value, self.triple_store)

        expected_result = SpecPassed(spec_uri, self.triple_store["type"])
        assert t == expected_result

    def test_insert_data_spec_passes(self):
        state = Graph()
        state.parse(data=self.given_sub_pred_obj, format="ttl")
        insert_data_query = """
        insert data { <https://semanticpartners.com/data/test/subject> <https://semanticpartners.com/data/test/predicate> <https://semanticpartners.com/data/test/object> }
        """
        spec_graph = Graph()
        spec = """
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

        test-data:my_first_spec 
            a must:TestSpec ;
            must:then  [ a must:StatementsDataSource ;
                 must:statements [ a             rdf:Statement ;
                                   rdf:subject   test-data:sub ;
                                   rdf:predicate test-data:pred ;
                                   rdf:object    test-data:obj ; ] ,
                                 [ a             rdf:Statement ;
                                   rdf:subject   test-data:subject ;
                                   rdf:predicate test-data:predicate ;
                                   rdf:object    test-data:object ; ] ; ] .
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_first_spec

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              folder_location=None,
                                              mustrd_triple_store=self.triple_store)

        t = run_update_spec(spec_uri, state, insert_data_query, then_component.value, self.triple_store)

        expected_result = SpecPassed(spec_uri, self.triple_store["type"])
        assert t == expected_result

    def test_delete_data_spec_passes(self):
        state = Graph()
        state.parse(data=self.given_sub_pred_obj, format="ttl")
        delete_data_query = """
        delete data { <https://semanticpartners.com/data/test/sub> <https://semanticpartners.com/data/test/pred> <https://semanticpartners.com/data/test/obj> }
        """
        spec_graph = Graph()
        spec = """
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

        test-data:my_first_spec 
            a must:TestSpec ;
            must:then  [ a must:EmptyGraphResult ] .
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_first_spec

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              folder_location=None,
                                              mustrd_triple_store=self.triple_store)

        t = run_update_spec(spec_uri, state, delete_data_query, then_component.value, self.triple_store)

        expected_result = SpecPassed(spec_uri, self.triple_store["type"])
        assert t == expected_result

    def test_delete_insert_spec_passes(self):
        state = Graph()
        state.parse(data=self.given_sub_pred_obj, format="ttl")
        delete_insert_query = """
        delete {?s ?p ?o} insert { ?o ?p ?s } where {?s ?p ?o}
        """
        spec_graph = Graph()
        spec = """
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

        test-data:my_first_spec 
            a must:TestSpec ;
            must:then  [ a must:StatementsDataSource ;
                 must:statements [ a             rdf:Statement ;
                                   rdf:subject   test-data:obj ;
                                   rdf:predicate test-data:pred ;
                                   rdf:object    test-data:sub ; ] ; ] .
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_first_spec

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              folder_location=None,
                                              mustrd_triple_store=self.triple_store)

        t = run_update_spec(spec_uri, state, delete_insert_query, then_component.value, self.triple_store)

        expected_result = SpecPassed(spec_uri, self.triple_store["type"])
        assert t == expected_result

    def test_insert_spec_fails_with_graph_comparison(self):
        state = Graph()
        state.parse(data=self.given_sub_pred_obj, format="ttl")
        insert_query = """
        insert { ?o ?p ?s } where {?s ?p ?o}
        """
        spec_graph = Graph()
        spec = """
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
        
        test-data:my_failing_insert_spec
            a must:TestSpec ;
            must:then  [ a must:StatementsDataSource ;
                         must:statements [ a             rdf:Statement ;
                                           rdf:subject   test-data:sub ;
                                           rdf:predicate test-data:pred ;
                                           rdf:object    test-data:obj ; ] ,
                                         [ a             rdf:Statement ;
                                           rdf:subject   test-data:obj ;
                                           rdf:predicate test-data:predicate ;
                                           rdf:object    test-data:sub ; ] ; ] .
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_insert_spec

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              folder_location=None,
                                              mustrd_triple_store=self.triple_store)

        result = run_update_spec(spec_uri, state, insert_query, then_component.value, self.triple_store)

        assert result.spec_uri == spec_uri

        expected_in_expected_not_in_actual = Graph()
        expected_in_expected_not_in_actual.add((TEST_DATA.obj, TEST_DATA.predicate, TEST_DATA.sub))

        expected_in_actual_not_in_expected = Graph()
        expected_in_actual_not_in_expected.add((TEST_DATA.obj, TEST_DATA.pred, TEST_DATA.sub))

        result_type = type(result)
        if result_type == UpdateSpecFailure:
            graph_comparison = result.graph_comparison
            assert isomorphic(graph_comparison.in_expected_not_in_actual,
                              expected_in_expected_not_in_actual), graph_comparison_message(
                expected_in_expected_not_in_actual, graph_comparison.in_expected_not_in_actual)
            assert isomorphic(graph_comparison.in_actual_not_in_expected,
                              expected_in_actual_not_in_expected), graph_comparison_message(
                expected_in_actual_not_in_expected, graph_comparison.in_actual_not_in_expected)
            assert len(graph_comparison.in_both.all_nodes()) == 2
        else:
            raise Exception(f"Unexpected result type {result_type}")

    def test_delete_spec_fails_with_graph_comparison(self):
        state = Graph()
        state.parse(data=self.given_sub_pred_obj, format="ttl")
        delete_query = """
        delete { ?s ?p ?obj } where {?s ?p ?o}
        """
        spec_graph = Graph()
        spec = """
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

        test-data:my_failing_delete_spec
            a must:TestSpec ;
            must:then  [ a must:EmptyGraphResult ] .
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_delete_spec

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              folder_location=None,
                                              mustrd_triple_store=self.triple_store)

        result = run_update_spec(spec_uri, state, delete_query, then_component.value, self.triple_store)

        assert result.spec_uri == spec_uri

        expected_in_expected_not_in_actual = Graph()

        expected_in_actual_not_in_expected = Graph()
        expected_in_actual_not_in_expected.add((TEST_DATA.sub, TEST_DATA.pred, TEST_DATA.obj))

        result_type = type(result)
        if result_type == UpdateSpecFailure:
            graph_comparison = result.graph_comparison
            assert isomorphic(graph_comparison.in_expected_not_in_actual,
                              expected_in_expected_not_in_actual), graph_comparison_message(
                expected_in_expected_not_in_actual, graph_comparison.in_expected_not_in_actual)
            assert isomorphic(graph_comparison.in_actual_not_in_expected,
                              expected_in_actual_not_in_expected), graph_comparison_message(
                expected_in_actual_not_in_expected, graph_comparison.in_actual_not_in_expected)
            assert len(graph_comparison.in_both.all_nodes()) == 0
        else:
            raise Exception(f"Unexpected result type {result_type}")

    def test_insert_data_spec_fails_with_graph_comparison(self):
        state = Graph()
        state.parse(data=self.given_sub_pred_obj, format="ttl")
        insert_data_query = """
        insert data { <https://semanticpartners.com/data/test/subject> <https://semanticpartners.com/data/test/predicate> <https://semanticpartners.com/data/test/object> }
        """
        spec_graph = Graph()
        spec = """
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

        test-data:my_failing_insert_data_spec
            a must:TestSpec ;
            must:then  [ a must:StatementsDataSource ;
                         must:statements [ a             rdf:Statement ;
                                           rdf:subject   test-data:subject ;
                                           rdf:predicate test-data:predicate ;
                                           rdf:object    test-data:object ; ] ; ] .
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_insert_data_spec

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              folder_location=None,
                                              mustrd_triple_store=self.triple_store)

        result = run_update_spec(spec_uri, state, insert_data_query, then_component.value, self.triple_store)

        assert result.spec_uri == spec_uri

        expected_in_expected_not_in_actual = Graph()

        expected_in_actual_not_in_expected = Graph()
        expected_in_actual_not_in_expected.add((TEST_DATA.sub, TEST_DATA.pred, TEST_DATA.obj))

        result_type = type(result)
        if result_type == UpdateSpecFailure:
            graph_comparison = result.graph_comparison
            assert isomorphic(graph_comparison.in_expected_not_in_actual,
                              expected_in_expected_not_in_actual), graph_comparison_message(
                expected_in_expected_not_in_actual, graph_comparison.in_expected_not_in_actual)
            assert isomorphic(graph_comparison.in_actual_not_in_expected,
                              expected_in_actual_not_in_expected), graph_comparison_message(
                expected_in_actual_not_in_expected, graph_comparison.in_actual_not_in_expected)
            assert len(graph_comparison.in_both.all_nodes()) == 2
        else:
            raise Exception(f"Unexpected result type {result_type}")

    def test_delete_data_spec_fails_with_graph_comparison(self):
        state = Graph()
        state.parse(data=self.given_sub_pred_obj, format="ttl")
        delete_data_query = """
        delete data { <https://semanticpartners.com/data/test/sub> <https://semanticpartners.com/data/test/pred> <https://semanticpartners.com/data/test/obj> }
        """
        spec_graph = Graph()
        spec = """
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

        test-data:my_failing_delete_data_spec
            a must:TestSpec ;
            must:then  [ a must:StatementsDataSource ;
                         must:statements [ a             rdf:Statement ;
                                           rdf:subject   test-data:sub ;
                                           rdf:predicate test-data:pred ;
                                           rdf:object    test-data:obj ; ] ; ].
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_delete_data_spec

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              folder_location=None,
                                              mustrd_triple_store=self.triple_store)

        result = run_update_spec(spec_uri, state, delete_data_query, then_component.value, self.triple_store)

        assert result.spec_uri == spec_uri

        expected_in_expected_not_in_actual = Graph()
        expected_in_expected_not_in_actual.add((TEST_DATA.sub, TEST_DATA.pred, TEST_DATA.obj))

        expected_in_actual_not_in_expected = Graph()

        result_type = type(result)
        if result_type == UpdateSpecFailure:
            graph_comparison = result.graph_comparison
            assert isomorphic(graph_comparison.in_expected_not_in_actual,
                              expected_in_expected_not_in_actual), graph_comparison_message(
                expected_in_expected_not_in_actual, graph_comparison.in_expected_not_in_actual)
            assert isomorphic(graph_comparison.in_actual_not_in_expected,
                              expected_in_actual_not_in_expected), graph_comparison_message(
                expected_in_actual_not_in_expected, graph_comparison.in_actual_not_in_expected)
            assert len(graph_comparison.in_both.all_nodes()) == 0
        else:
            raise Exception(f"Unexpected result type {result_type}")

    def test_delete_insert_data_spec_fails_with_graph_comparison(self):
        state = Graph()
        state.parse(data=self.given_sub_pred_obj, format="ttl")
        delete_insert_query = """
        delete {?s ?p ?o} insert { ?o ?p ?s } where {?s ?p ?o}
        """
        spec_graph = Graph()
        spec = """
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

        test-data:my_failing_delete_insert_spec
            a must:TestSpec ;
            must:then  [ a must:StatementsDataSource ;
                         must:statements [ a             rdf:Statement ;
                                           rdf:subject   test-data:sub ;
                                           rdf:predicate test-data:pred ;
                                           rdf:object    test-data:obj ; ] ; ] .
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_delete_insert_spec

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              folder_location=None,
                                              mustrd_triple_store=self.triple_store)

        result = run_update_spec(spec_uri, state, delete_insert_query, then_component.value, self.triple_store)

        assert result.spec_uri == spec_uri

        expected_in_expected_not_in_actual = Graph()
        expected_in_expected_not_in_actual.add((TEST_DATA.sub, TEST_DATA.pred, TEST_DATA.obj))

        expected_in_actual_not_in_expected = Graph()
        expected_in_actual_not_in_expected.add((TEST_DATA.obj, TEST_DATA.pred, TEST_DATA.sub))

        result_type = type(result)
        if result_type == UpdateSpecFailure:
            graph_comparison = result.graph_comparison
            assert isomorphic(graph_comparison.in_expected_not_in_actual,
                              expected_in_expected_not_in_actual), graph_comparison_message(
                expected_in_expected_not_in_actual, graph_comparison.in_expected_not_in_actual)
            assert isomorphic(graph_comparison.in_actual_not_in_expected,
                              expected_in_actual_not_in_expected), graph_comparison_message(
                expected_in_actual_not_in_expected, graph_comparison.in_actual_not_in_expected)
            assert len(graph_comparison.in_both.all_nodes()) == 0
        else:
            raise Exception(f"Unexpected result type {result_type}")

    def test_insert_with_variables_and_optional_spec_passes(self):
        triples = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        test-data:sub1 test-data:pred test-data:obj .
        test-data:sub2 test-data:pred test-data:obj ; test-data:predicate test-data:object .
        """
        state = Graph()
        state.parse(data=triples, format="ttl")

        insert_query = """
        insert { ?s ?p ?o ; ?pred ?obj . } where { ?s ?p ?o OPTIONAL { ?s ?pred ?obj } }
        """
        binding = {Variable('p'): URIRef("https://semanticpartners.com/data/test/pred"),
                   Variable('pred'): URIRef("https://semanticpartners.com/data/test/predicate")}
        spec_graph = Graph()
        spec = """
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

        test-data:my_first_spec 
            a must:TestSpec ;
            must:then [ a must:StatementsDataSource ;
                        must:statements [
                            a rdf:Statement ;
                            rdf:subject test-data:sub1 ;
                            rdf:predicate test-data:pred ;
                            rdf:object test-data:obj ;
                        ] , 
                        [
                            a rdf:Statement ;
                            rdf:subject test-data:sub2 ;
                            rdf:predicate test-data:pred ;
                            rdf:object test-data:obj ;
                        ] ,
                        [
                            a rdf:Statement ;
                            rdf:subject test-data:sub2 ;
                            rdf:predicate test-data:predicate ;
                            rdf:object test-data:object ;
                        ] ; ] .
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_first_spec

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              folder_location=None,
                                              mustrd_triple_store=self.triple_store)

        t = run_update_spec(spec_uri, state, insert_query, then_component.value, self.triple_store, binding)

        expected_result = SpecPassed(spec_uri, self.triple_store["type"])
        assert t == expected_result

    def test_delete_insert_with_variables_spec_passes(self):
        triples = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        test-data:sub test-data:pred "hello world" , test-data:obj .
        """
        state = Graph()
        state.parse(data=triples, format="ttl")

        delete_insert_query = """
        delete { ?s ?p ?o } insert { ?s <https://semanticpartners.com/data/test/predicate> ?o } where { ?s ?p ?o }
        """
        binding = {Variable('o'): Literal('hello world')}
        spec_graph = Graph()
        spec = """
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

        test-data:my_first_spec 
            a must:TestSpec ;
            must:then  [ a must:StatementsDataSource ;
                        must:statements [
                            a rdf:Statement ;
                            rdf:subject test-data:sub ;
                            rdf:predicate test-data:predicate ;
                            rdf:object "hello world" ;
                        ] , 
                        [
                            a rdf:Statement ;
                            rdf:subject test-data:sub ;
                            rdf:predicate test-data:pred ;
                            rdf:object test-data:obj ;
                        ] ; ] .
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_first_spec

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              folder_location=None,
                                              mustrd_triple_store=self.triple_store)

        t = run_update_spec(spec_uri, state, delete_insert_query, then_component.value, self.triple_store, binding)

        expected_result = SpecPassed(spec_uri, self.triple_store["type"])
        assert t == expected_result

    def test_insert_statement_spec_fails(self):
        state = Graph()
        state.parse(data=self.given_sub_pred_obj, format="ttl")
        insert_query = """insert ?s ?p ?o where { typo }"""
        spec_graph = Graph()
        spec = """
        @prefix sh: <http://www.w3.org/ns/shacl#> .
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .

        test-data:my_failing_spec 
           a must:TestSpec ;
           must:then  [ a must:TableDataSource ;
                        must:rows [ sh:order 1 ;
                                    must:row [
                                       must:variable "s" ;
                                       must:binding test-data:wrong-subject ; 
                                        ] ; ] ; ].
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_spec

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              folder_location=None,
                                              mustrd_triple_store=self.triple_store)

        spec_result = run_update_spec(spec_uri, state, insert_query, then_component.value, self.triple_store)

        if type(spec_result) == SparqlParseFailure:
            assert spec_result.spec_uri == spec_uri
            assert str(
                spec_result.exception) == "Expected end of text, found 'insert'  (at char 0), (line:1, col:1)"
        else:
            raise Exception(f"wrong spec result type {spec_result}")

    def test_delete_insert_multiline_result_spec_passes(self):
        triples = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        test-data:sub test-data:pred test-data:obj .
        test-data:subject test-data:predicate test-data:object .
        """
        state = Graph()
        state.parse(data=triples, format="ttl")

        delete_insert_query = """
        delete { ?s ?p ?o } insert { ?o ?p ?s } where { ?s ?p ?o }
        """
        spec_graph = Graph()
        spec = """
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

        test-data:my_first_spec 
            a must:TestSpec ;
            must:then  [ a must:StatementsDataSource ;
                        must:statements [
                            a rdf:Statement ;
                            rdf:subject test-data:obj ;
                            rdf:predicate test-data:pred ;
                            rdf:object test-data:sub ; ] ,
                        [
                            a rdf:Statement ;
                            rdf:subject test-data:object ;
                            rdf:predicate test-data:predicate ;
                            rdf:object test-data:subject ; ] ;
                             ] .
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_first_spec

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              folder_location=None,
                                              mustrd_triple_store=self.triple_store)

        t = run_update_spec(spec_uri, state, delete_insert_query, then_component.value, self.triple_store)

        expected_result = SpecPassed(spec_uri, self.triple_store["type"])
        assert t == expected_result
