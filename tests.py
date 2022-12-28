from mustrd import Given, When, run_scenario, ScenarioPass
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

        expected_result = ScenarioPass(URIRef("https://semanticpartners.com/data/test/my-first-scenario"))
        assert t == expected_result

