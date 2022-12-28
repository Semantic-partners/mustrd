import logging
from dataclasses import dataclass
from pyparsing import ParseException

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
class GraphComparison:
    in_expected_not_in_actual: Graph
    in_actual_not_in_expected: Graph
    in_both: Graph


@dataclass
class ScenarioResult:
    scenario_uri: URIRef


@dataclass
class ScenarioFailure(ScenarioResult):
    graph_comparison: GraphComparison


@dataclass
class SparqlParseFailure(ScenarioResult):
    exception: ParseException


def run_spec(scenario_graph: Graph, g: Given, w: When) -> ScenarioResult:
    scenario_uri = list(scenario_graph.subjects(RDF.type, MUST.TestSpec))[0]
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
    try:
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

        graph_compare = graph_comparison(scenario, g)
        equal = isomorphic(g, scenario)
        if equal:
            return ScenarioResult(scenario_uri)
        else:
            return ScenarioFailure(scenario_uri, graph_compare)
    except ParseException as e:
        return SparqlParseFailure(scenario_uri, e)


def graph_comparison(expected_graph, actual_graph) -> GraphComparison:
    diff = graph_diff(expected_graph, actual_graph)
    in_both = diff[0]
    in_expected = diff[1]
    in_actual = diff[2]
    in_expected_not_in_actual = (in_expected - in_actual)
    in_actual_not_in_expected = (in_actual - in_expected)
    return GraphComparison(in_expected_not_in_actual, in_actual_not_in_expected, in_both)


def get_initial_state(spec_uri: URIRef, spec_graph: Graph) -> Graph:
    given_query = f"""CONSTRUCT {{ ?s ?p ?o }} WHERE {{ {spec_uri} <{MUST.given}> [ a <{RDF.Statement}> ; <{RDF.subject}> ?s ; <{RDF.predicate}> ?p ; <{RDF.object}> ?o ; ] }}"""
    initial_state = spec_graph.query(given_query).graph
    return initial_state
