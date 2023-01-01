from rdflib import Graph
from rdflib.namespace import Namespace

from mustrd import run_select_spec, SpecPassed, SelectSpecFailure, SparqlParseFailure, SelectSparqlQuery, get_then_select

TEST_DATA = Namespace("https://semanticpartners.com/data/test/")


class TestRunSelectSpec:
    def test_select_spec_passes(self):
        triples = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        test-data:sub test-data:pred test-data:obj .
        """

        state = Graph()
        state.parse(data=triples, format="ttl")
        select_query = """
        select ?s ?p ?o { ?s ?p ?o }
        """
        spec_graph = Graph()
        spec = """
        @prefix sh: <http://www.w3.org/ns/shacl#> .
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        
        test-data:my_first_spec 
            a must:TestSpec ;
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
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_first_spec

        then_df = get_then_select(spec_uri, spec_graph)
        t = run_select_spec(spec_uri, state, SelectSparqlQuery(select_query), then_df)

        expected_result = SpecPassed(spec_uri)
        assert t == expected_result

    def test_select_spec_fails_with_expected_vs_actual_table_comparison(self):
        triples = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        test-data:sub test-data:pred test-data:obj .
        """
        state = Graph()
        state.parse(data=triples, format="ttl")
        select_query = """
        select ?s ?p ?o { ?s ?p ?o }
        """
        spec_graph = Graph()
        spec = """
        @prefix sh: <http://www.w3.org/ns/shacl#> .
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        
        test-data:my_failing_spec 
            a must:TestSpec ;
            must:then [
                sh:order 1 ;
                must:results [
                   must:variable "s" ;
                   must:binding test-data:wrong-subject ; 
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
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_spec

        then_df = get_then_select(spec_uri, spec_graph)
        spec_result = run_select_spec(spec_uri, state, SelectSparqlQuery(select_query), then_df)

        if type(spec_result) == SelectSpecFailure:
            table_diff = spec_result.table_comparison.to_markdown()
            assert spec_result.spec_uri == spec_uri
            assert table_diff == """|    | ('s', 'expected')                                    | ('s', 'actual')                            |
|---:|:-----------------------------------------------------|:-------------------------------------------|
|  0 | https://semanticpartners.com/data/test/wrong-subject | https://semanticpartners.com/data/test/sub |"""
        else:
            raise Exception(f"wrong spec result type {spec_result}")

    def test_select_spec_fails_for_different_types(self):
        triples = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        test-data:sub test-data:pred 1 .
        """
        state = Graph()
        state.parse(data=triples, format="ttl")
        select_query = """
        select ?s ?p ?o { ?s ?p ?o }
        """
        spec_graph = Graph()
        spec = """
        @prefix sh: <http://www.w3.org/ns/shacl#> .
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        
        test-data:my_failing_spec 
            a must:TestSpec ;
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
                   must:binding 1.0  ; 
                    ];
                ] .
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_spec

        then_df = get_then_select(spec_uri, spec_graph)
        spec_result = run_select_spec(spec_uri, state, SelectSparqlQuery(select_query), then_df)

        if type(spec_result) == SelectSpecFailure:
            table_diff = spec_result.table_comparison.to_markdown()
            assert spec_result.spec_uri == spec_uri
            assert table_diff == """|    |   ('o', 'expected') |   ('o', 'actual') | ('o_datatype', 'expected')               | ('o_datatype', 'actual')                 |
|---:|--------------------:|------------------:|:-----------------------------------------|:-----------------------------------------|
|  0 |                   1 |                 1 | http://www.w3.org/2001/XMLSchema#decimal | http://www.w3.org/2001/XMLSchema#integer |"""
        else:
            raise Exception(f"wrong spec result type {spec_result}")

    def test_invalid_select_statement_spec_fails(self):
        triples = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        test-data:sub test-data:pred test-data:obj .
        """
        state = Graph()
        state.parse(data=triples, format="ttl")
        select_query = """select ?s ?p ?o { typo }"""
        spec_graph = Graph()
        spec = """
        @prefix sh: <http://www.w3.org/ns/shacl#> .
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        
        test-data:my_failing_spec 
           a must:TestSpec ;
            must:then [
                sh:order 1 ;
                must:results [
                   must:variable "s" ;
                   must:binding test-data:wrong-subject ; 
                    ] ;
                ] .
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_spec

        then_df = get_then_select(spec_uri, spec_graph)
        spec_result = run_select_spec(spec_uri, state, SelectSparqlQuery(select_query), then_df)

        if type(spec_result) == SparqlParseFailure:
            assert spec_result.spec_uri == spec_uri
            assert str(spec_result.exception) == "Expected {SelectQuery | ConstructQuery | DescribeQuery | AskQuery}, found 'typo'  (at char 18), (line:1, col:19)"
        else:
            raise Exception(f"wrong spec result type {spec_result}")
