import pandas

from mustrd import run_select_spec, ScenarioResult, SelectSpecFailure, SparqlParseFailure, get_given, get_when, SelectSparqlQuery, get_then_select, run_construct_spec, get_then_construct, ConstructSparqlQuery
from rdflib import Graph
from rdflib.compare import isomorphic, graph_diff
from rdflib.namespace import Namespace

TEST_DATA = Namespace("https://semanticpartners.com/data/test/")


class TestRunSelectSpec:
    def test_select_scenario_passes(self):
        triples = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        test-data:sub test-data:pred test-data:obj .
        """

        state = Graph()
        state.parse(data=triples, format="ttl")
        select_query = """
        select ?s ?p ?o { ?s ?p ?o }
        """
        scenario_graph = Graph()
        scenario = """
        @prefix sh: <http://www.w3.org/ns/shacl#> .
        @prefix must: <https://semanticpartners.com/mustrd/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        
        test-data:my_first_scenario 
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
        scenario_graph.parse(data=scenario, format='ttl')

        spec_uri = TEST_DATA.my_first_scenario

        then_df = get_then_select(spec_uri, scenario_graph)
        t = run_select_spec(spec_uri, state, SelectSparqlQuery(select_query), then_df)

        expected_result = ScenarioResult(spec_uri)
        assert t == expected_result

    def test_select_scenario_fails_with_expected_vs_actual_graph_comparison(self):
        triples = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        test-data:sub test-data:pred test-data:obj .
        """
        state = Graph()
        state.parse(data=triples, format="ttl")
        select_query = """
        select ?s ?p ?o { ?s ?p ?o }
        """
        scenario_graph = Graph()
        scenario = """
        @prefix sh: <http://www.w3.org/ns/shacl#> .
        @prefix must: <https://semanticpartners.com/mustrd/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        
        test-data:my_failing_scenario 
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
        scenario_graph.parse(data=scenario, format='ttl')

        spec_uri = TEST_DATA.my_failing_scenario

        then_df = get_then_select(spec_uri, scenario_graph)
        scenario_result = run_select_spec(spec_uri, state, SelectSparqlQuery(select_query), then_df)

        if type(scenario_result) == SelectSpecFailure:
            table_diff = scenario_result.table_comparison.to_markdown()
            assert scenario_result.scenario_uri == spec_uri
            assert table_diff == """|    | ('s', 'expected')                                    | ('s', 'actual')                            |
|---:|:-----------------------------------------------------|:-------------------------------------------|
|  0 | https://semanticpartners.com/data/test/wrong-subject | https://semanticpartners.com/data/test/sub |"""
        else:
            raise Exception(f"wrong scenario result type {scenario_result}")

    def test_invalid_select_statement_scenario_fails(self):
        triples = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        test-data:sub test-data:pred test-data:obj .
        """
        state = Graph()
        state.parse(data=triples, format="ttl")
        select_query = """select ?s ?p ?o { typo }"""
        scenario_graph = Graph()
        scenario = """
        @prefix sh: <http://www.w3.org/ns/shacl#> .
        @prefix must: <https://semanticpartners.com/mustrd/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        
        test-data:my_failing_scenario 
           a must:TestSpec ;
            must:then [
                sh:order 1 ;
                must:results [
                   must:variable "s" ;
                   must:binding test-data:wrong-subject ; 
                    ] ;
                ] .
        """
        scenario_graph.parse(data=scenario, format='ttl')

        spec_uri = TEST_DATA.my_failing_scenario

        then_df = get_then_select(spec_uri, scenario_graph)
        scenario_result = run_select_spec(spec_uri, state, SelectSparqlQuery(select_query), then_df)

        if type(scenario_result) == SparqlParseFailure:
            assert scenario_result.scenario_uri == spec_uri
            assert str(scenario_result.exception) == "Expected {SelectQuery | ConstructQuery | DescribeQuery | AskQuery}, found 'typo'  (at char 18), (line:1, col:19)"
        else:
            raise Exception(f"wrong scenario result type {scenario_result}")


class TestRunConstructSpec:
    def test_construct_scenario_passes(self):
        triples = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        test-data:sub test-data:pred test-data:obj .
        """

        state = Graph()
        state.parse(data=triples, format="ttl")
        construct_query = """
        construct { ?o ?s ?p } { ?s ?p ?o }
        """
        scenario_graph = Graph()
        scenario = """
        @prefix must: <https://semanticpartners.com/mustrd/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
        
        test-data:my_first_scenario 
            a must:TestSpec ;
            must:then [
                    a rdf:Statement ;
                    rdf:subject test-data:obj ;
                    rdf:predicate test-data:sub ;
                    rdf:object test-data:pred ;
                ] .
        """
        scenario_graph.parse(data=scenario, format='ttl')

        spec_uri = TEST_DATA.my_first_scenario

        then_df = get_then_construct(spec_uri, scenario_graph)
        t = run_construct_spec(spec_uri, state, ConstructSparqlQuery(construct_query), then_df)

        expected_result = ScenarioResult(spec_uri)
        assert t == expected_result


class TestSpecParserTest:

    select_spec_uri = TEST_DATA.a_complete_select_scenario
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

    construct_spec_uri = TEST_DATA.a_construct_scenario
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

