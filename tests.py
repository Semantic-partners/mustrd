from mustrd import Given, When, run_scenario, ScenarioResult, ScenarioFailure
from rdflib import Graph, URIRef


class TestMustrd:
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
        
        test-data:my-first-scenario 
            a must:TestScenario ;
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

        g = Given(state)
        w = When(select_query)

        t = run_scenario(scenario_graph, g, w)

        expected_result = ScenarioResult(URIRef("https://semanticpartners.com/data/test/my-first-scenario"))
        assert t == expected_result

    def test_select_scenario_fails_with_message(self):
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
        
        test-data:my-failing-scenario 
            a must:TestScenario ;
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

        g = Given(state)
        w = When(select_query)

        scenario_result = run_scenario(scenario_graph, g, w)

        if type(scenario_result) == ScenarioFailure:
            graph_comparison = scenario_result.graph_comparison
            assert scenario_result.scenario_uri == URIRef("https://semanticpartners.com/data/test/my-failing-scenario")
            assert graph_comparison.in_expected_not_in_actual.serialize(format='ttl') == """@prefix ns1: <https://semanticpartners.com/mustrd/> .

[] ns1:binding <https://semanticpartners.com/data/test/wrong-subject> .

"""
            assert graph_comparison.in_actual_not_in_expected.serialize(format='ttl') == """@prefix ns1: <https://semanticpartners.com/mustrd/> .

[] ns1:binding <https://semanticpartners.com/data/test/sub> .

"""

