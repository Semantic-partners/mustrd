from mustrd import Given, When, run_spec, ScenarioResult, ScenarioFailure, SparqlParseFailure, get_initial_state
from rdflib import Graph, URIRef
from rdflib.compare import isomorphic, graph_diff

class TestRunMustrdSpec:
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

        g = Given(state)
        w = When(select_query)

        t = run_spec(scenario_graph, g, w)

        expected_result = ScenarioResult(URIRef("https://semanticpartners.com/data/test/my-first-scenario"))
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
        
        test-data:my-failing-scenario 
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

        g = Given(state)
        w = When(select_query)

        scenario_result = run_spec(scenario_graph, g, w)

        if type(scenario_result) == ScenarioFailure:
            graph_comparison = scenario_result.graph_comparison
            assert scenario_result.scenario_uri == URIRef("https://semanticpartners.com/data/test/my-failing-scenario")
            assert graph_comparison.in_expected_not_in_actual.serialize(format='ttl') == """@prefix ns1: <https://semanticpartners.com/mustrd/> .

[] ns1:binding <https://semanticpartners.com/data/test/wrong-subject> .

"""
            assert graph_comparison.in_actual_not_in_expected.serialize(format='ttl') == """@prefix ns1: <https://semanticpartners.com/mustrd/> .

[] ns1:binding <https://semanticpartners.com/data/test/sub> .

"""
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
        
        test-data:my-failing-scenario 
            a must:TestSpec .
        """
        scenario_graph.parse(data=scenario, format='ttl')

        g = Given(state)
        w = When(select_query)

        scenario_result = run_spec(scenario_graph, g, w)

        if type(scenario_result) == SparqlParseFailure:
            assert scenario_result.scenario_uri == URIRef("https://semanticpartners.com/data/test/my-failing-scenario")
            assert str(scenario_result.exception) == "Expected {SelectQuery | ConstructQuery | DescribeQuery | AskQuery}, found 'typo'  (at char 18), (line:1, col:19)"
        else:
            raise Exception(f"wrong scenario result type {scenario_result}")


class TestSpecParserTest:

    spec_uri = URIRef("<https://semanticpartners.com/data/test/a-complete-select-scenario>")
    spec = f"""
            @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
            @prefix sh: <http://www.w3.org/ns/shacl#> .
            @prefix must: <https://semanticpartners.com/mustrd/> .
            @prefix test-data: <https://semanticpartners.com/data/test/> .
            
            
            {spec_uri}
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
        spec_graph.parse(data=self.spec, format='ttl')
        givens = get_initial_state(self.spec_uri, spec_graph)

        expected_triples = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        test-data:sub test-data:pred test-data:obj .
        """
        expected_initial_state = Graph()
        expected_initial_state.parse(data=expected_triples, format='ttl')

        assert isomorphic(givens, expected_initial_state), graph_comparison_message(expected_initial_state, givens)

    # def test_when(self):


def graph_comparison_message(expected_graph, actual_graph) -> str:
    diff = graph_diff(expected_graph, actual_graph)
    in_expected = diff[1]
    in_actual = diff[2]
    in_expected_not_in_actual = (in_expected - in_actual).serialize(format='ttl')
    in_actual_not_in_expected = (in_actual - in_expected).serialize(format='ttl')
    in_both = diff[0].serialize(format='ttl')
    message = f"in_expected_not_in_actual\n{in_expected_not_in_actual}\nin_actual_not_in_expected\n{in_actual_not_in_expected}\nin_both\n{in_both}"
    return message

