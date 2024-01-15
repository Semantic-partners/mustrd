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

import os
from pathlib import Path

from rdflib import Graph, Variable, Literal
from rdflib.namespace import Namespace
from rdflib.compare import isomorphic

from mustrd import SpecPassed, ConstructSpecFailure, SparqlParseFailure, graph_comparison as mustrd_graph_comparison, \
    UpdateSpecFailure, check_result, Specification
from steprunner import run_when
from graph_util import graph_comparison_message
from namespace import MUST
from spec_component import get_spec_component_from_file, ThenSpec, TableThenSpec, parse_spec_component
from utils import get_project_root

TEST_DATA = Namespace("https://semanticpartners.com/data/test/")


class TestRunConstructSpec:
    given_sub_pred_obj = """
    @prefix test-data: <https://semanticpartners.com/data/test/> .
    test-data:sub test-data:pred test-data:obj .
    """

    triple_store = {"type": MUST.RdfLib}

    def test_construct_spec_passes(self):
        run_config = {}
        state = Graph()
        state.parse(data=self.given_sub_pred_obj, format="ttl")
        spec_graph = Graph()
        spec = f"""
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
        
        test-data:my_first_spec 
            a must:TestSpec ;
                    must:when  [ a must:TextSparqlSource ;
                 must:queryText  "construct {{ ?o ?s ?p }} where {{ ?s ?p ?o }}" ;
                 must:queryType must:ConstructSparql  ; ] ;
                must:then  [ a must:StatementsDataset ;
                 must:hasStatement [ a             rdf:Statement ;
                                   rdf:subject   test-data:obj ;
                                   rdf:predicate test-data:sub ;
                                   rdf:object    test-data:pred ; ] ; ] .
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_first_spec

        when_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.when,
                                              spec_graph=spec_graph,
                                              run_config=run_config,
                                              mustrd_triple_store=self.triple_store)

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              run_config=run_config,
                                              mustrd_triple_store=self.triple_store)

        self.triple_store["given"] = state
        result = run_when(spec_uri, self.triple_store, when_component[0])
        assert isomorphic(result, then_component.value)
        assert type(then_component) == ThenSpec

    def test_construct_spec_fails_with_graph_comparison(self):
        run_config = {}
        given = Graph()
        given.parse(data=self.given_sub_pred_obj, format="ttl")
        spec_graph = Graph()
        spec = """
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
        
        test-data:my_failing_construct_spec 
            a must:TestSpec ;
                                must:when  [ a must:TextSparqlSource ;
                 must:queryText  "construct { ?p ?o ?s } where { ?s ?p ?o }" ;
                                  must:queryType must:ConstructSparql  ; ] ;
            must:then  [ a must:StatementsDataset ;
                 must:hasStatement [ a             rdf:Statement ;
                                   rdf:subject   test-data:obj ;
                                   rdf:predicate test-data:sub ;
                                   rdf:object    test-data:pred ; ] ;  ] .
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_construct_spec
        when_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.when,
                                              spec_graph=spec_graph,
                                              run_config=run_config,
                                              mustrd_triple_store=self.triple_store)

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              run_config=run_config,
                                              mustrd_triple_store=self.triple_store)

        self.triple_store["given"] = given
        spec = Specification(spec_uri, self.triple_store, given, when_component, then_component)
        when_result = run_when(spec_uri, self.triple_store, when_component[0])
        then_result = check_result(spec, when_result)

        assert then_result.spec_uri == spec_uri
        assert type(then_component) == ThenSpec

        expected_in_expected_not_in_actual = Graph()
        expected_in_expected_not_in_actual.add((TEST_DATA.obj, TEST_DATA.sub, TEST_DATA.pred))

        expected_in_actual_not_in_expected = Graph()
        expected_in_actual_not_in_expected.add((TEST_DATA.pred, TEST_DATA.obj, TEST_DATA.sub))

        result_type = type(then_result)
        if result_type == ConstructSpecFailure:
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

    def test_construct_with_variables_spec_passes(self):
        run_config = {}
        triples = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        test-data:sub test-data:pred "hello world" , test-data:obj .
        """
        state = Graph()
        state.parse(data=triples, format="ttl")

        construct_query = """
        construct { ?s ?p ?o } { ?s ?p ?o }
        """
        binding = {Variable('o'): Literal('hello world')}
        spec_graph = Graph()
        spec = """
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

        test-data:my_first_spec 
            a must:TestSpec ;
            must:then  [ a must:StatementsDataset ;
                        must:hasStatement [
                            a rdf:Statement ;
                            rdf:subject test-data:sub ;
                            rdf:predicate test-data:pred ;
                            rdf:object "hello world" ;
                        ] ; ] .
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_first_spec

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              run_config=run_config,
                                              mustrd_triple_store=self.triple_store)

        t = run_construct_spec(spec_uri, state, construct_query, then_component.value, self.triple_store,
                               bindings=binding)

        expected_result = SpecPassed(spec_uri, self.triple_store["type"])
        assert t == expected_result
        assert type(then_component) == ThenSpec

    def test_construct_spec_with_variable_fails_with_graph_comparison(self):
        run_config = {}
        triples = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        test-data:sub test-data:pred "hello world" .
        """
        state = Graph()
        state.parse(data=triples, format="ttl")

        construct_query = """
        construct { ?s ?p ?o } { ?s ?p ?o }
        """
        binding = {Variable('o'): Literal('hello world')}
        spec_graph = Graph()
        spec = """
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

        test-data:my_failing_construct_spec 
            a must:TestSpec ;
            must:then  [ a must:StatementsDataset ;
                        must:hasStatement [
                            a rdf:Statement ;
                            rdf:subject test-data:sub ;
                            rdf:predicate test-data:pred ;
                            rdf:object test-data:obj ;
                        ] ; ] .
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_construct_spec

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              run_config=run_config,
                                              mustrd_triple_store=self.triple_store)

        result = run_construct_spec(spec_uri, state, construct_query, then_component.value, self.triple_store,
                                    bindings=binding)

        assert result.spec_uri == spec_uri
        assert type(then_component) == ThenSpec

        expected_in_expected_not_in_actual = Graph()
        expected_in_expected_not_in_actual.add((TEST_DATA.sub, TEST_DATA.pred, TEST_DATA.obj))

        expected_in_actual_not_in_expected = Graph()
        expected_in_actual_not_in_expected.add((TEST_DATA.sub, TEST_DATA.pred, Literal("hello world")))

        result_type = type(result)
        if result_type == ConstructSpecFailure:
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

    def test_construct_expect_empty_result_spec_passes(self):
        run_config = {}
        state = Graph()
        state.parse(data=self.given_sub_pred_obj, format="ttl")
        construct_query = """
        construct { ?s ?p ?o } { ?s ?p ?o }
        """
        binding = {Variable('o'): Literal('hello world')}
        spec_graph = Graph()
        spec = """
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

        test-data:my_first_spec 
            a must:TestSpec ;
                  must:then  [ a must:EmptyGraph ] .
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_first_spec

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              run_config=run_config,
                                              mustrd_triple_store=self.triple_store)

        t = run_construct_spec(spec_uri, state, construct_query, then_component.value, self.triple_store,
                               bindings=binding)

        expected_result = SpecPassed(spec_uri, self.triple_store["type"])
        assert t == expected_result
        assert type(then_component) == ThenSpec

    def test_construct_unexpected_result_spec_fails(self):
        run_config = {}
        state = Graph()
        state.parse(data=self.given_sub_pred_obj, format="ttl")
        construct_query = """
        construct { ?s ?p ?o } { ?s ?p ?o }
        """
        spec_graph = Graph()
        spec = """
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

        test-data:my_failing_construct_spec
            a must:TestSpec ;
                must:then  [ a must:EmptyGraph ] .

        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_construct_spec

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              run_config=run_config,
                                              mustrd_triple_store=self.triple_store)

        result = run_construct_spec(spec_uri, state, construct_query, then_component.value, self.triple_store)

        assert result.spec_uri == spec_uri
        assert type(then_component) == ThenSpec

        expected_in_expected_not_in_actual = Graph()

        expected_in_actual_not_in_expected = Graph()
        expected_in_actual_not_in_expected.add((TEST_DATA.sub, TEST_DATA.pred, TEST_DATA.obj))

        result_type = type(result)
        if result_type == ConstructSpecFailure:
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

    def test_construct_unexpected_empty_result_spec_fails(self):
        run_config = {}
        state = Graph()
        state.parse(data=self.given_sub_pred_obj, format="ttl")
        construct_query = """
        construct { ?s ?p ?o } { ?s ?p ?o }
        """
        binding = {Variable('o'): Literal('hello world')}
        spec_graph = Graph()
        spec = """
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

        test-data:my_failing_construct_spec
            a must:TestSpec ;
                must:then  [ a must:StatementsDataset ;
                        must:hasStatement [
                            a rdf:Statement ;
                            rdf:subject test-data:sub ;
                            rdf:predicate test-data:pred ;
                            rdf:object test-data:obj ;
                        ] ; ] .
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_construct_spec

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              run_config=run_config,
                                              mustrd_triple_store=self.triple_store)

        result = run_construct_spec(spec_uri, state, construct_query, then_component.value, self.triple_store,
                                    bindings=binding)

        assert result.spec_uri == spec_uri
        assert type(then_component) == ThenSpec

        expected_in_expected_not_in_actual = Graph()
        expected_in_expected_not_in_actual.add((TEST_DATA.sub, TEST_DATA.pred, TEST_DATA.obj))

        expected_in_actual_not_in_expected = Graph()

        result_type = type(result)
        if result_type == ConstructSpecFailure:
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

    def test_construct_multiline_result_spec_passes(self):
        run_config = {}
        triples = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        test-data:sub test-data:pred test-data:obj .
        test-data:subject test-data:predicate test-data:object .
        """
        state = Graph()
        state.parse(data=triples, format="ttl")

        construct_query = """
        construct { ?o ?p ?s } { ?s ?p ?o }
        """
        spec_graph = Graph()
        spec = """
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

        test-data:my_first_spec 
            a must:TestSpec ;
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
                            rdf:object test-data:subject ; ] ; ] .
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_first_spec

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              run_config=run_config,
                                              mustrd_triple_store=self.triple_store)

        t = run_construct_spec(spec_uri, state, construct_query, then_component.value, self.triple_store)

        expected_result = SpecPassed(spec_uri, self.triple_store["type"])
        assert t == expected_result
        assert type(then_component) == ThenSpec

    def test_construct_spec_result_mismatch_fails_with_graph_comparison(self):
        run_config = {}
        triples = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        test-data:sub test-data:pred test-data:obj .
        test-data:subject test-data:predicate test-data:object .
        """
        state = Graph()
        state.parse(data=triples, format="ttl")

        construct_query = """
        construct { ?o ?p ?s } { ?s ?p ?o }
        """
        spec_graph = Graph()
        spec = """
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

        test-data:my_failing_construct_spec
            a must:TestSpec ;
            must:then  [ a must:StatementsDataset ;
                        must:hasStatement [
                            a rdf:Statement ;
                            rdf:subject test-data:obj ;
                            rdf:predicate test-data:pred ;
                            rdf:object test-data:sub ; ] ;
                             ] .
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_construct_spec

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              run_config=run_config,
                                              mustrd_triple_store=self.triple_store)

        result = run_construct_spec(spec_uri, state, construct_query, then_component.value, self.triple_store)

        assert result.spec_uri == spec_uri
        assert type(then_component) == ThenSpec

        expected_in_expected_not_in_actual = Graph()

        expected_in_actual_not_in_expected = Graph()
        expected_in_actual_not_in_expected.add((TEST_DATA.object, TEST_DATA.predicate, TEST_DATA.subject))

        result_type = type(result)
        if result_type == ConstructSpecFailure:
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

    def test_construct_statement_spec_fails(self):
        run_config = {}
        state = Graph()
        state.parse(data=self.given_sub_pred_obj, format="ttl")
        construct_query = """construct ?s ?p ?o where { typo }"""
        spec_graph = Graph()
        spec = """
        @prefix sh: <http://www.w3.org/ns/shacl#> .
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .

        test-data:my_failing_spec 
           a must:TestSpec ;
            must:then  [ a must:TableDataset ;
                        must:hasRow [ sh:order 1 ;
                                    must:hasBinding[
                                       must:variable "s" ;
                                       must:boundValue test-data:wrong-subject ; 
                                        ] ; ] ; ].
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_spec

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              run_config=run_config,
                                              mustrd_triple_store=self.triple_store)

        spec_result = run_construct_spec(spec_uri, state, construct_query, then_component.value, self.triple_store)

        if type(spec_result) == SparqlParseFailure:
            assert type(then_component) == TableThenSpec
            assert spec_result.spec_uri == spec_uri
            assert str(
                spec_result.exception) == "Expected {SelectQuery | ConstructQuery | DescribeQuery | AskQuery}, found '?'  (at char 10), (line:1, col:11)"
        else:
            raise Exception(f"wrong spec result type {spec_result}")

    def test_construct_when_file_spec_passes(self):

        state = Graph()
        state.parse(data=self.given_sub_pred_obj, format="ttl")
        project_root = get_project_root()
        when_path = "test/data/construct.rq"
        run_config = {'when_path': "test/data/construct.rq"}
        file_path = Path(os.path.join(project_root, when_path))
        construct_query = get_spec_component_from_file(file_path)

        spec_graph = Graph()
        spec = """
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

        test-data:my_first_spec 
            a must:TestSpec ;
                must:then  [ a must:StatementsDataset ;
                 must:hasStatement [ a             rdf:Statement ;
                                   rdf:subject   test-data:obj ;
                                   rdf:predicate test-data:sub ;
                                   rdf:object    test-data:pred ; ] ; ] .
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_first_spec

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              run_config=run_config,
                                              mustrd_triple_store=self.triple_store)

        t = run_construct_spec(spec_uri, state, construct_query, then_component.value, self.triple_store)

        expected_result = SpecPassed(spec_uri, self.triple_store["type"])
        assert t == expected_result
        assert type(then_component) == ThenSpec

    def test_construct_given_then_files_spec_passes(self):
        project_root = get_project_root()
        when_path = "test/data/construct.rq"
        file_path = Path(os.path.join(project_root, when_path))
        construct_query = get_spec_component_from_file(file_path)
        run_config = {'given_path': Path(os.path.join(project_root, "test/data/construct.rq")),
                      'spec_path': Path(os.path.join(project_root, "test"))}

        spec_graph = Graph()
        spec = """
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

        test-data:my_first_spec 
            a must:TestSpec ;
                must:given [ a must:StatementsDataset ;
                                   must:hasStatement [ a rdf:Statement ;
                                                     rdf:subject   test-data:sub1 ;
                                                     rdf:predicate test-data:pred1 ;
                                                     rdf:object    test-data:obj1 ; ] ; ] ,
                            [ a must:FileDataset ;
                            must:file "data/given.ttl"  ] ;
                must:then  [ a must:StatementsDataset ;
                 must:hasStatement [ a             rdf:Statement ;
                                   rdf:subject   test-data:obj1 ;
                                   rdf:predicate test-data:sub1 ;
                                   rdf:object    test-data:pred1 ; ] ; ] ; 
                 must:then  [ a must:FileDataset ;
                                   must:file "data/thenSuccess.nt" ] .
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_first_spec

        given_component = parse_spec_component(subject=spec_uri,
                                               predicate=MUST.given,
                                               spec_graph=spec_graph,
                                               run_config=run_config,
                                               mustrd_triple_store=self.triple_store)

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              run_config=run_config,
                                              mustrd_triple_store=self.triple_store)

        t = run_construct_spec(spec_uri, given_component.value, construct_query, then_component.value,
                               self.triple_store)

        expected_result = SpecPassed(spec_uri, self.triple_store["type"])
        assert t == expected_result
        assert type(then_component) == ThenSpec

    def test_construct_when_file_from_folder_spec_passes(self):
        state = Graph()
        state.parse(data=self.given_sub_pred_obj, format="ttl")

        project_root = get_project_root()
        run_config = {'when_path': Path(os.path.join(project_root, "test/data"))}
        spec_graph = Graph()
        spec = """
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

        test-data:my_first_spec 
            a must:TestSpec ;
                must:when [ a must:FolderSparqlSource ;
                            must:fileName "construct.rq" ;
                            must:queryType must:ConstructSparql ; ] ;
                must:then  [ a must:StatementsDataset ;
                             must:hasStatement [ a             rdf:Statement ;
                                   rdf:subject   test-data:obj ;
                                   rdf:predicate test-data:sub ;
                                   rdf:object    test-data:pred ; ] ; ] .
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_first_spec

        when_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.when,
                                              spec_graph=spec_graph,
                                              run_config=run_config,
                                              mustrd_triple_store=self.triple_store)

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              run_config=run_config,
                                              mustrd_triple_store=self.triple_store)

        t = run_construct_spec(spec_uri, state, when_component[0].value, then_component.value, self.triple_store)

        expected_result = SpecPassed(spec_uri, self.triple_store["type"])
        assert t == expected_result
        assert type(then_component) == ThenSpec

