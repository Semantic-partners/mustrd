import logging
from dataclasses import dataclass
from pyparsing import ParseException
from itertools import groupby

from rdflib import Graph, BNode, Literal, URIRef
from rdflib.namespace import SH, RDF
from rdflib.compare import isomorphic, graph_diff
import pandas

from namespace import MUST

@dataclass
class GraphComparison:
    in_expected_not_in_actual: Graph
    in_actual_not_in_expected: Graph
    in_both: Graph


@dataclass
class ScenarioResult:
    scenario_uri: URIRef

@dataclass
class SelectSpecFailure(ScenarioResult):
    table_comparison: pandas.DataFrame


@dataclass
class ConstructSpecFailure(ScenarioResult):
    graph_comparison: GraphComparison


@dataclass
class SparqlParseFailure(ScenarioResult):
    exception: ParseException


@dataclass
class SelectSparqlQuery:
    query: str


@dataclass
class ConstructSparqlQuery:
    query: str


def run_select_spec(spec_uri: URIRef,
                    given: Graph,
                    when: SelectSparqlQuery,
                    then: pandas.DataFrame) -> ScenarioResult:
    logging.info(f"Running select spec {spec_uri}")

    try:
        result = given.query(when.query)

        frames = []
        for item in result:
            columns = []
            values = []
            for key, value in item.asdict().items():
                columns.append(key)
                values.append(value)
            frames.append(pandas.DataFrame([values], columns=columns))

            df = pandas.concat(frames, ignore_index=True)
            df_diff = then.compare(df, result_names=("expected", "actual"))

            if df_diff.empty:
                return ScenarioResult(spec_uri)
            else:
                return SelectSpecFailure(spec_uri, df_diff)

    except ParseException as e:
        return SparqlParseFailure(spec_uri, e)


def run_construct_spec(spec_uri: URIRef,
                       given: Graph,
                       when: ConstructSparqlQuery,
                       then: Graph):
    logging.info(f"Running construct spec {spec_uri}")
    result = given.query(when.query).graph

    graph_compare = graph_comparison(then, result)
    equal = isomorphic(result, then)
    if equal:
        return ScenarioResult(spec_uri)
    else:
        return ConstructSpecFailure(spec_uri, graph_compare)


def graph_comparison(expected_graph, actual_graph) -> GraphComparison:
    diff = graph_diff(expected_graph, actual_graph)
    in_both = diff[0]
    in_expected = diff[1]
    in_actual = diff[2]
    in_expected_not_in_actual = (in_expected - in_actual)
    in_actual_not_in_expected = (in_actual - in_expected)
    return GraphComparison(in_expected_not_in_actual, in_actual_not_in_expected, in_both)


def get_initial_state(spec_uri: URIRef, spec_graph: Graph) -> Graph:
    given_query = f"""CONSTRUCT {{ ?s ?p ?o }} WHERE {{ <{spec_uri}> <{MUST.given}> [ a <{RDF.Statement}> ; <{RDF.subject}> ?s ; <{RDF.predicate}> ?p ; <{RDF.object}> ?o ; ] }}"""
    initial_state = spec_graph.query(given_query).graph
    return initial_state


def get_when(spec_uri: URIRef, spec_graph: Graph) -> SelectSparqlQuery:
    when_query = f"""SELECT ?type ?query {{ <{spec_uri}> <{MUST.when}> [ a ?type ; <{MUST.query}> ?query ; ] }}"""
    whens = spec_graph.query(when_query)
    for when in whens:
        if when.type == MUST.SelectSparql:
            return SelectSparqlQuery(when.query.value)


def get_construct_then(spec_uri: URIRef, spec_graph: Graph) -> Graph:
    then_query = f"""
    prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> 
    
    CONSTRUCT {{ ?s ?p ?o }}
    {{
        <{spec_uri}> <{MUST.then}> [
            a rdf:Statement ;
            rdf:subject ?s ;
            rdf:predicate ?p ;
            rdf:object ?o ;
        ]
    }}
    """
    expected_results = spec_graph.query(then_query).graph

    return expected_results


def get_select_then(spec_uri: URIRef, spec_graph: Graph) -> pandas.DataFrame:
    then_query = f"""
    prefix sh: <http://www.w3.org/ns/shacl#> 
    prefix must: <https://semanticpartners.com/mustrd/> 
    
    SELECT ?then ?order ?variable ?binding
    WHERE {{ 
        <{spec_uri}> <{MUST.then}> ?then .
        ?then 
            sh:order ?order ;
            must:results [
                must:variable ?variable ;
                must:binding ?binding ;
            ] .
        }}"""

    expected_results = spec_graph.query(then_query)

    frames = []
    for then, items in groupby(expected_results, lambda er: er.then):
        columns = []
        values = []
        for i in list(items):
            columns.append(i.variable.value)
            values.append(i.binding)
        frames.append(pandas.DataFrame([values], columns=columns))

    df = pandas.concat(frames, ignore_index=True)
    return df
