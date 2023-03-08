from rdflib import Graph, Variable, Literal
from rdflib.namespace import Namespace
from rdflib.compare import isomorphic

from mustrd import SpecPassed, run_construct_spec, get_then_construct, ConstructSparqlQuery, ConstructSpecFailure, \
    SparqlParseFailure
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
                must:then  [ must:dataSource [ a must:StatementsDataSource ;
                 must:statements [ a             rdf:Statement ;
                                   rdf:subject   test-data:obj ;
                                   rdf:predicate test-data:sub ;
                                   rdf:object    test-data:pred ; ] ; ] ; ] .
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
            must:then  [ must:dataSource [ a must:StatementsDataSource ;
                 must:statements [ a             rdf:Statement ;
                                   rdf:subject   test-data:obj ;
                                   rdf:predicate test-data:sub ;
                                   rdf:object    test-data:pred ; ] ; ] ; ] .
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

    def test_construct_with_variables_spec_passes(self):
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
            must:then  [ must:dataSource [ a must:StatementsDataSource ;
                        must:statements [
                            a rdf:Statement ;
                            rdf:subject test-data:sub ;
                            rdf:predicate test-data:pred ;
                            rdf:object "hello world" ;
                        ] ; ] ; ] .
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_first_spec

        then_df = get_then_construct(spec_uri, spec_graph)
        t = run_construct_spec(spec_uri, state, ConstructSparqlQuery(construct_query), then_df, binding)

        expected_result = SpecPassed(spec_uri)
        assert t == expected_result

    def test_construct_spec_with_variable_fails_with_graph_comparison(self):
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
            must:then  [ must:dataSource [ a must:StatementsDataSource ;
                        must:statements [
                            a rdf:Statement ;
                            rdf:subject test-data:sub ;
                            rdf:predicate test-data:pred ;
                            rdf:object test-data:obj ;
                        ] ; ] ; ] .
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_construct_spec

        then_df = get_then_construct(spec_uri, spec_graph)
        result = run_construct_spec(spec_uri, state, ConstructSparqlQuery(construct_query), then_df, binding)

        assert result.spec_uri == spec_uri

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
        triples = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        test-data:sub test-data:pred test-data:obj .
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
                  must:then  [ must:dataSource [ a must:EmptyResult ] ; ] .
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_first_spec

        then_df = get_then_construct(spec_uri, spec_graph)
        t = run_construct_spec(spec_uri, state, ConstructSparqlQuery(construct_query), then_df, binding)

        expected_result = SpecPassed(spec_uri)
        assert t == expected_result

    def test_construct_unexpected_result_spec_fails(self):
        triples = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        test-data:sub test-data:pred test-data:obj .
        """

        state = Graph()
        state.parse(data=triples, format="ttl")
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
                must:then  [ must:dataSource [ a must:EmptyResult ] ; ] .

        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_construct_spec

        then_df = get_then_construct(spec_uri, spec_graph)
        result = run_construct_spec(spec_uri, state, ConstructSparqlQuery(construct_query), then_df)

        assert result.spec_uri == spec_uri

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
        triples = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        test-data:sub test-data:pred test-data:obj .
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
                must:then  [ must:dataSource [ a must:StatementsDataSource ;
                        must:statements [
                            a rdf:Statement ;
                            rdf:subject test-data:sub ;
                            rdf:predicate test-data:pred ;
                            rdf:object test-data:obj ;
                        ] ; ] ; ] .
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_construct_spec

        then_df = get_then_construct(spec_uri, spec_graph)
        result = run_construct_spec(spec_uri, state, ConstructSparqlQuery(construct_query), then_df, binding)

        assert result.spec_uri == spec_uri

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
            must:then  [ must:dataSource [ a must:StatementsDataSource ;
                        must:statements [
                            a rdf:Statement ;
                            rdf:subject test-data:obj ;
                            rdf:predicate test-data:pred ;
                            rdf:object test-data:sub ; ] ,
                        [
                            a rdf:Statement ;
                            rdf:subject test-data:object ;
                            rdf:predicate test-data:predicate ;
                            rdf:object test-data:subject ; ] ; ] ;
                             ] .
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_first_spec

        then_df = get_then_construct(spec_uri, spec_graph)
        t = run_construct_spec(spec_uri, state, ConstructSparqlQuery(construct_query), then_df)

        expected_result = SpecPassed(spec_uri)
        assert t == expected_result

    def test_construct_spec_result_mismatch_fails_with_graph_comparison(self):
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
            must:then  [ must:dataSource [ a must:StatementsDataSource ;
                        must:statements [
                            a rdf:Statement ;
                            rdf:subject test-data:obj ;
                            rdf:predicate test-data:pred ;
                            rdf:object test-data:sub ; ] ; ] ;
                             ] .
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_construct_spec

        then_df = get_then_construct(spec_uri, spec_graph)
        result = run_construct_spec(spec_uri, state, ConstructSparqlQuery(construct_query), then_df)

        assert result.spec_uri == spec_uri

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
        triples = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        test-data:sub test-data:pred test-data:obj .
        """
        state = Graph()
        state.parse(data=triples, format="ttl")
        construct_query = """construct ?s ?p ?o where { typo }"""
        spec_graph = Graph()
        spec = """
        @prefix sh: <http://www.w3.org/ns/shacl#> .
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .

        test-data:my_failing_spec 
           a must:TestSpec ;
            must:then  [ must:dataSource [ a must:TableDataSource ;
                        must:rows [ sh:order 1 ;
                                    must:row [
                                       must:variable "s" ;
                                       must:binding test-data:wrong-subject ; 
                                        ] ; ] ; ] ; ].
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_spec

        then_df = get_then_construct(spec_uri, spec_graph)
        spec_result = run_construct_spec(spec_uri, state, ConstructSparqlQuery(construct_query), then_df)

        if type(spec_result) == SparqlParseFailure:
            assert spec_result.spec_uri == spec_uri
            assert str(
                spec_result.exception) == "Expected {SelectQuery | ConstructQuery | DescribeQuery | AskQuery}, found '?'  (at char 10), (line:1, col:11)"
        else:
            raise Exception(f"wrong spec result type {spec_result}")