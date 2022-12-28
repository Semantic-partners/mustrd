import logging
from dataclasses import dataclass

from rdflib import Graph, BNode, Literal, URIRef
from rdflib.namespace import SH, RDF
from rdflib.compare import isomorphic, graph_diff

from namespace import MUST


@dataclass
class Given:
    graph: Graph


@dataclass
class When:
    query: str


@dataclass
class Then:
    graph: Graph


@dataclass
class ScenarioPass:
    scenarioUri: URIRef


def run_scenario(scenario_graph: Graph, g: Given, w: When) -> ScenarioPass:
    scenario_uri = list(scenario_graph.subjects(RDF.type, MUST.TestScenario))[0]
    scenario_query = f"""
    CONSTRUCT {{?then ?p1 ?o1 . ?o1 ?p2 ?o2 . }} 
    WHERE {{ 
        <{scenario_uri}> <{MUST.then}> ?then . 
        ?then ?p1 ?o1 . 
        OPTIONAL {{
            ?o1 ?p2 ?o2 . 
            }}
        }}"""
    scenario = scenario_graph.query(scenario_query).graph
    logging.info(f"Running scenario {scenario_uri}")
    result = g.graph.query(w.query)
    g = Graph()
    for pos, row in enumerate(result, 1):
        row_node = BNode()
        g.add((row_node, SH.order, Literal(pos)))
        results = row.asdict().items()
        for key, value in results:
            column_node = BNode()
            g.add((row_node, MUST.results, column_node))
            g.add((column_node, MUST.variable, Literal(key)))
            g.add((column_node, MUST.binding, value))

    message = error_message(scenario, g)
    equal = isomorphic(g, scenario)
    if equal:
        return ScenarioPass(scenario_uri)


def error_message(expected_graph, actual_graph) -> str:
    diff = graph_diff(expected_graph, actual_graph)
    in_both = diff[0]
    in_expected = diff[1]
    in_actual = diff[2]
    in_expected_not_in_actual = (in_expected - in_actual).serialize(format='ttl')
    in_actual_not_in_expected = (in_actual - in_expected).serialize(format='ttl')
    return f"in_expected_not_in_actual\n{in_expected_not_in_actual}\nin_actual_not_in_expected\n{in_actual_not_in_expected}\nin_both\n{in_both}"
