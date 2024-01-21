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
from pyparsing import ParseException
from rdflib import Graph
from rdflib.namespace import Namespace
from rdflib.compare import isomorphic

from mustrd import SpecPassed, UpdateSpecFailure, SparqlParseFailure, SpecSkipped, \
    Specification, check_result
from graph_util import graph_comparison_message
from namespace import MUST
from spec_component import parse_spec_component
from steprunner import run_when

TEST_DATA = Namespace("https://semanticpartners.com/data/test/")


class TestRunUpdateSpec:
    given_sub_pred_obj = """
    @prefix test-data: <https://semanticpartners.com/data/test/> .
    test-data:sub test-data:pred test-data:obj .
    """

    triple_store = {"type": MUST.RdfLib}

    def test_insert_spec_passes(self):

        given = Graph().parse(data=self.given_sub_pred_obj, format="ttl")
        query = "insert { ?o ?p ?s } where {?s ?p ?o}"
        spec = f"""
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
        
        test-data:my_first_spec 
            a must:TestSpec ;
            must:when  [ a  must:TextSparqlSource ;
                                must:queryText  "{query}" ; 
                                must:queryType must:UpdateSparql  ;
                                ] ; 
            must:then  [ a must:StatementsDataset ;
                 must:hasStatement [ a             rdf:Statement ;
                                   rdf:subject   test-data:sub ;
                                   rdf:predicate test-data:pred ;
                                   rdf:object    test-data:obj ; ] ,
                                 [ a             rdf:Statement ;
                                   rdf:subject   test-data:obj ;
                                   rdf:predicate test-data:pred ;
                                   rdf:object    test-data:sub ; ] ; ] .
        """
        spec_graph = Graph().parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_first_spec
        when_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.when,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        self.triple_store["given"] = given
        spec = Specification(spec_uri, self.triple_store, given, when_component, then_component)
        when_result = run_when(spec_uri, self.triple_store, when_component[0])
        then_result = check_result(spec, when_result)
        expected_result = SpecPassed(spec_uri, self.triple_store["type"])
        assert then_result == expected_result

    def test_delete_spec_passes(self):

        given = Graph().parse(data=self.given_sub_pred_obj, format="ttl")
        query ="delete { ?s ?p ?o } where {?s ?p ?o}"
        spec = f"""
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

        test-data:my_first_spec 
            a must:TestSpec ;
                        must:when  [ a  must:TextSparqlSource ;
                                must:queryText  "{query}" ; 
                                must:queryType must:UpdateSparql  ;
                                ] ; 
                  must:then  [ a must:EmptyGraph ] .
        """
        spec_graph = Graph().parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_first_spec

        when_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.when,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        self.triple_store["given"] = given
        spec = Specification(spec_uri, self.triple_store, given, when_component, then_component)
        when_result = run_when(spec_uri, self.triple_store, when_component[0])
        then_result = check_result(spec, when_result)
        expected_result = SpecPassed(spec_uri, self.triple_store["type"])
        assert then_result == expected_result

    def test_insert_data_spec_passes(self):

        given = Graph().parse(data=self.given_sub_pred_obj, format="ttl")
        query = "insert data { <https://semanticpartners.com/data/test/subject> <https://semanticpartners.com/data/test/predicate> <https://semanticpartners.com/data/test/object> }"
        spec = f"""
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

        test-data:my_first_spec 
            a must:TestSpec ;
            must:when  [ a  must:TextSparqlSource ;
                                must:queryText  "{query}" ; 
                                must:queryType must:UpdateSparql  ;
                                ] ; 
            must:then  [ a must:StatementsDataset ;
                 must:hasStatement [ a             rdf:Statement ;
                                   rdf:subject   test-data:sub ;
                                   rdf:predicate test-data:pred ;
                                   rdf:object    test-data:obj ; ] ,
                                 [ a             rdf:Statement ;
                                   rdf:subject   test-data:subject ;
                                   rdf:predicate test-data:predicate ;
                                   rdf:object    test-data:object ; ] ; ] .
        """
        spec_graph = Graph().parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_first_spec

        when_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.when,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        self.triple_store["given"] = given
        spec = Specification(spec_uri, self.triple_store, given, when_component, then_component)
        when_result = run_when(spec_uri, self.triple_store, when_component[0])
        then_result = check_result(spec, when_result)

        expected_result = SpecPassed(spec_uri, self.triple_store["type"])
        assert then_result == expected_result

    def test_delete_data_spec_passes(self):
        given = Graph().parse(data=self.given_sub_pred_obj, format="ttl")
        query = "delete data { <https://semanticpartners.com/data/test/sub> <https://semanticpartners.com/data/test/pred> <https://semanticpartners.com/data/test/obj> }"
        spec = f"""
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

        test-data:my_first_spec 
            a must:TestSpec ;
            must:when  [ a  must:TextSparqlSource ;
                                must:queryText  "{query}" ; 
                                must:queryType must:UpdateSparql  ;
                                ] ; 
            must:then  [ a must:EmptyGraph ] .
        """
        spec_graph = Graph().parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_first_spec

        when_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.when,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        self.triple_store["given"] = given
        spec = Specification(spec_uri, self.triple_store, given, when_component, then_component)
        when_result = run_when(spec_uri, self.triple_store, when_component[0])
        then_result = check_result(spec, when_result)

        expected_result = SpecPassed(spec_uri, self.triple_store["type"])
        assert then_result == expected_result

    def test_delete_insert_spec_passes(self):

        given = Graph().parse(data=self.given_sub_pred_obj, format="ttl")
        query = "delete {?s ?p ?o} insert { ?o ?p ?s } where {?s ?p ?o}"
        spec = f"""
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

        test-data:my_first_spec 
            a must:TestSpec ;
                        must:when  [ a  must:TextSparqlSource ;
                                must:queryText  "{query}" ; 
                                must:queryType must:UpdateSparql  ;
                                ] ; 
            must:then  [ a must:StatementsDataset ;
                 must:hasStatement [ a             rdf:Statement ;
                                   rdf:subject   test-data:obj ;
                                   rdf:predicate test-data:pred ;
                                   rdf:object    test-data:sub ; ] ; ] .
        """
        spec_graph = Graph().parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_first_spec

        when_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.when,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        self.triple_store["given"] = given
        spec = Specification(spec_uri, self.triple_store, given, when_component, then_component)
        when_result = run_when(spec_uri, self.triple_store, when_component[0])
        then_result = check_result(spec, when_result)

        expected_result = SpecPassed(spec_uri, self.triple_store["type"])
        assert then_result == expected_result

    def test_insert_spec_fails_with_graph_comparison(self):

        given = Graph().parse(data=self.given_sub_pred_obj, format="ttl")
        query = "insert { ?o ?p ?s } where {?s ?p ?o}"
        spec = f"""
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
        
        test-data:my_failing_insert_spec
            a must:TestSpec ;
                                    must:when  [ a  must:TextSparqlSource ;
                                must:queryText  "{query}" ; 
                                must:queryType must:UpdateSparql  ;
                                ] ; 
            must:then  [ a must:StatementsDataset ;
                         must:hasStatement [ a             rdf:Statement ;
                                           rdf:subject   test-data:sub ;
                                           rdf:predicate test-data:pred ;
                                           rdf:object    test-data:obj ; ] ,
                                         [ a             rdf:Statement ;
                                           rdf:subject   test-data:obj ;
                                           rdf:predicate test-data:predicate ;
                                           rdf:object    test-data:sub ; ] ; ] .
        """
        spec_graph = Graph().parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_insert_spec

        when_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.when,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        then_component = parse_spec_component(subject=spec_uri,
                                          predicate=MUST.then,
                                          spec_graph=spec_graph,
                                          run_config=None,
                                          mustrd_triple_store=self.triple_store)

        self.triple_store["given"] = given
        spec = Specification(spec_uri, self.triple_store, given, when_component, then_component)
        when_result = run_when(spec_uri, self.triple_store, when_component[0])
        then_result = check_result(spec, when_result)

        assert then_result.spec_uri == spec_uri

        expected_in_expected_not_in_actual = Graph()
        expected_in_expected_not_in_actual.add((TEST_DATA.obj, TEST_DATA.predicate, TEST_DATA.sub))

        expected_in_actual_not_in_expected = Graph()
        expected_in_actual_not_in_expected.add((TEST_DATA.obj, TEST_DATA.pred, TEST_DATA.sub))

        result_type = type(then_result)
        if result_type == UpdateSpecFailure:
            graph_comparison = then_result.graph_comparison
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

        given = Graph().parse(data=self.given_sub_pred_obj, format="ttl")
        query = "delete { ?s ?p ?obj } where {?s ?p ?o}"
        spec = f"""
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

        test-data:my_failing_delete_spec
            a must:TestSpec ;
                                    must:when  [ a  must:TextSparqlSource ;
                                must:queryText  "{query}" ; 
                                must:queryType must:UpdateSparql  ;
                                ] ; 
            must:then  [ a must:EmptyGraph ] .
        """
        spec_graph = Graph().parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_delete_spec

        when_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.when,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        self.triple_store["given"] = given
        spec = Specification(spec_uri, self.triple_store, given, when_component, then_component)
        when_result = run_when(spec_uri, self.triple_store, when_component[0])
        then_result = check_result(spec, when_result)

        assert then_result.spec_uri == spec_uri

        expected_in_expected_not_in_actual = Graph()

        expected_in_actual_not_in_expected = Graph()
        expected_in_actual_not_in_expected.add((TEST_DATA.sub, TEST_DATA.pred, TEST_DATA.obj))

        result_type = type(then_result)
        if result_type == UpdateSpecFailure:
            graph_comparison = then_result.graph_comparison
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

        given = Graph().parse(data=self.given_sub_pred_obj, format="ttl")
        query = "insert data { <https://semanticpartners.com/data/test/subject> <https://semanticpartners.com/data/test/predicate> <https://semanticpartners.com/data/test/object> }"

        spec = f"""
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

        test-data:my_failing_insert_data_spec
            a must:TestSpec ;
                        must:when  [ a  must:TextSparqlSource ;
                                must:queryText  "{query}" ; 
                                must:queryType must:UpdateSparql  ;
                                ] ; 
            must:then  [ a must:StatementsDataset ;
                         must:hasStatement [ a             rdf:Statement ;
                                           rdf:subject   test-data:subject ;
                                           rdf:predicate test-data:predicate ;
                                           rdf:object    test-data:object ; ] ; ] .
        """
        spec_graph = Graph().parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_insert_data_spec

        when_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.when,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        self.triple_store["given"] = given
        spec = Specification(spec_uri, self.triple_store, given, when_component, then_component)
        when_result = run_when(spec_uri, self.triple_store, when_component[0])
        then_result = check_result(spec, when_result)

        assert then_result.spec_uri == spec_uri

        expected_in_expected_not_in_actual = Graph()

        expected_in_actual_not_in_expected = Graph()
        expected_in_actual_not_in_expected.add((TEST_DATA.sub, TEST_DATA.pred, TEST_DATA.obj))

        result_type = type(then_result)
        if result_type == UpdateSpecFailure:
            graph_comparison = then_result.graph_comparison
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

        given = Graph().parse(data=self.given_sub_pred_obj, format="ttl")
        query = "delete data { <https://semanticpartners.com/data/test/sub> <https://semanticpartners.com/data/test/pred> <https://semanticpartners.com/data/test/obj> }"

        spec = f"""
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

        test-data:my_failing_delete_data_spec
            a must:TestSpec ;
                        must:when  [ a  must:TextSparqlSource ;
                                must:queryText  "{query}" ; 
                                must:queryType must:UpdateSparql  ;
                                ] ; 
            must:then  [ a must:StatementsDataset ;
                         must:hasStatement [ a             rdf:Statement ;
                                           rdf:subject   test-data:sub ;
                                           rdf:predicate test-data:pred ;
                                           rdf:object    test-data:obj ; ] ; ].
        """
        spec_graph = Graph().parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_delete_data_spec

        when_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.when,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        self.triple_store["given"] = given
        spec = Specification(spec_uri, self.triple_store, given, when_component, then_component)
        when_result = run_when(spec_uri, self.triple_store, when_component[0])
        then_result = check_result(spec, when_result)

        assert then_result.spec_uri == spec_uri

        expected_in_expected_not_in_actual = Graph()
        expected_in_expected_not_in_actual.add((TEST_DATA.sub, TEST_DATA.pred, TEST_DATA.obj))

        expected_in_actual_not_in_expected = Graph()

        result_type = type(then_result)
        if result_type == UpdateSpecFailure:
            graph_comparison = then_result.graph_comparison
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

        given = Graph().parse(data=self.given_sub_pred_obj, format="ttl")
        query = "delete {?s ?p ?o} insert { ?o ?p ?s } where {?s ?p ?o}"
        spec = f"""
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

        test-data:my_failing_delete_insert_spec
            a must:TestSpec ;
                        must:when  [ a  must:TextSparqlSource ;
                                must:queryText  "{query}" ; 
                                must:queryType must:UpdateSparql  ;
                                ] ; 
            must:then  [ a must:StatementsDataset ;
                         must:hasStatement [ a             rdf:Statement ;
                                           rdf:subject   test-data:sub ;
                                           rdf:predicate test-data:pred ;
                                           rdf:object    test-data:obj ; ] ; ] .
        """
        spec_graph = Graph().parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_delete_insert_spec

        when_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.when,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        self.triple_store["given"] = given
        spec = Specification(spec_uri, self.triple_store, given, when_component, then_component)
        when_result = run_when(spec_uri, self.triple_store, when_component[0])
        then_result = check_result(spec, when_result)

        assert then_result.spec_uri == spec_uri

        expected_in_expected_not_in_actual = Graph()
        expected_in_expected_not_in_actual.add((TEST_DATA.sub, TEST_DATA.pred, TEST_DATA.obj))

        expected_in_actual_not_in_expected = Graph()
        expected_in_actual_not_in_expected.add((TEST_DATA.obj, TEST_DATA.pred, TEST_DATA.sub))

        result_type = type(then_result)
        if result_type == UpdateSpecFailure:
            graph_comparison = then_result.graph_comparison
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
        given = Graph().parse(data=triples, format="ttl")
        query = "insert { ?s ?p ?o ; ?pred ?obj . } where { ?s ?p ?o OPTIONAL { ?s ?pred ?obj } }"
        # query.bindings = {Variable('p'): URIRef("https://semanticpartners.com/data/test/pred"),
        #                   Variable('pred'): URIRef("https://semanticpartners.com/data/test/predicate")}
        spec = f"""
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

        test-data:my_first_spec 
            a must:TestSpec ;
                        must:when  [ a  must:TextSparqlSource ;
                                must:queryText  "{query}" ; 
                                must:queryType must:UpdateSparql  ;
                                must:hasBinding [ must:variable "p" ;
                                            must:boundValue  test-data:pred ; ] ;
                                must:hasBinding [ must:variable "pred" ;
                                            must:boundValue  test-data:predicate ; ] ;
                                ] ; 
            must:then [ a must:StatementsDataset ;
                        must:hasStatement [
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
        spec_graph = Graph().parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_first_spec

        when_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.when,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        self.triple_store["given"] = given
        spec = Specification(spec_uri, self.triple_store, given, when_component, then_component)
        when_result = run_when(spec_uri, self.triple_store, when_component[0])
        then_result = check_result(spec, when_result)

        expected_result = SpecPassed(spec_uri, self.triple_store["type"])
        assert then_result == expected_result

    def test_delete_insert_with_variables_spec_passes(self):
        triples = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        test-data:sub test-data:pred "hello world" , test-data:obj .
        """
        given = Graph().parse(data=triples, format="ttl")

        query = "delete { ?s ?p ?o } insert { ?s <https://semanticpartners.com/data/test/predicate> ?o } where { ?s ?p ?o }"

        # query.bindings = {Variable('o'): Literal('hello world')}
        spec = f"""
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

        test-data:my_first_spec 
            a must:TestSpec ;
                        must:when  [ a  must:TextSparqlSource ;
                                must:queryText  "{query}" ; 
                                must:queryType must:UpdateSparql  ;
                                must:hasBinding [ must:variable "o" ;
                                            must:boundValue  "hello world" ; ] ;
                                ] ; 
            must:then  [ a must:StatementsDataset ;
                        must:hasStatement [
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
        spec_graph = Graph().parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_first_spec

        when_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.when,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        self.triple_store["given"] = given
        spec = Specification(spec_uri, self.triple_store, given, when_component, then_component)
        when_result = run_when(spec_uri, self.triple_store, when_component[0])
        then_result = check_result(spec, when_result)

        expected_result = SpecPassed(spec_uri, self.triple_store["type"])
        assert then_result == expected_result

    def test_insert_statement_spec_fails(self):
        given = Graph().parse(data=self.given_sub_pred_obj, format="ttl")
        query = "insert ?s ?p ?o where { typo }"
        spec = f"""
        @prefix sh: <http://www.w3.org/ns/shacl#> .
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .

        test-data:my_failing_spec 
           a must:TestSpec ;
                       must:when  [ a  must:TextSparqlSource ;
                                must:queryText  "{query}" ; 
                                must:queryType must:UpdateSparql  ;
                                ] ; 
           must:then  [ a must:TableDataset ;
                        must:hasRow [ sh:order 1 ;
                                    must:hasBinding[
                                       must:variable "s" ;
                                       must:boundValue test-data:wrong-subject ; 
                                        ] ; ] ; ].
        """
        spec_graph = Graph().parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_spec

        when_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.when,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        self.triple_store["given"] = given
        spec = Specification(spec_uri, self.triple_store, given, when_component, then_component)
        try:
            when_result = run_when(spec_uri, self.triple_store, when_component[0])
        except ParseException as e:
            when_result = SparqlParseFailure(spec_uri, self.triple_store["type"], e)
        if type(when_result) == SparqlParseFailure:
            assert when_result.spec_uri == spec_uri
            assert str(
                when_result.exception) == "Expected end of text, found 'insert'  (at char 0), (line:1, col:1)"
        else:
            raise Exception(f"wrong spec result type {when_result}")

    def test_delete_insert_multiline_result_spec_passes(self):
        triples = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        test-data:sub test-data:pred test-data:obj .
        test-data:subject test-data:predicate test-data:object .
        """
        given = Graph().parse(data=triples, format="ttl")
        query = "delete { ?s ?p ?o } insert { ?o ?p ?s } where { ?s ?p ?o }"
        spec = f"""
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

        test-data:my_first_spec 
            a must:TestSpec ;
                        must:when  [ a  must:TextSparqlSource ;
                                must:queryText  "{query}" ; 
                                must:queryType must:UpdateSparql  ;
                                ] ; 
            must:then  [ a must:StatementsDataset ;
                        must:hasStatement [
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
        spec_graph = Graph().parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_first_spec

        when_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.when,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        self.triple_store["given"] = given
        spec = Specification(spec_uri, self.triple_store, given, when_component, then_component)
        when_result = run_when(spec_uri, self.triple_store, when_component[0])
        then_result = check_result(spec, when_result)

        expected_result = SpecPassed(spec_uri, self.triple_store["type"])
        assert then_result == expected_result

    def test_insert_spec_not_implemented_skipped(self):
        triple_store = {"type": MUST.NotImplemented}
        given = Graph().parse(data=self.given_sub_pred_obj, format="ttl")
        query = "insert { ?o ?p ?s } where {?s ?p ?o}"

        spec = f"""
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

        test-data:my_first_spec 
            a must:TestSpec ;
                        must:when  [ a  must:TextSparqlSource ;
                                must:queryText  "{query}" ; 
                                must:queryType must:UpdateSparql  ;
                                ] ; 
            must:then  [ a must:StatementsDataset ;
                 must:hasStatement [ a             rdf:Statement ;
                                   rdf:subject   test-data:sub ;
                                   rdf:predicate test-data:pred ;
                                   rdf:object    test-data:obj ; ] ,
                                 [ a             rdf:Statement ;
                                   rdf:subject   test-data:obj ;
                                   rdf:predicate test-data:pred ;
                                   rdf:object    test-data:sub ; ] ; ] .
        """
        spec_graph = Graph().parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_first_spec

        when_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.when,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        triple_store["given"] = given
        try:
            when_result = run_when(spec_uri, triple_store, when_component[0])
        except NotImplementedError as ex:
            when_result = SpecSkipped(spec_uri, triple_store, ex.args[0])
        expected_result = SpecSkipped(spec_uri, triple_store, f"{when_component[0].queryType} not implemented for {triple_store['type']}")
        assert when_result == expected_result


