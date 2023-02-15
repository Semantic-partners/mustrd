import logging
from dataclasses import dataclass
from pyparsing import ParseException
from itertools import groupby
from pathlib import Path

from rdflib import Graph, URIRef, Variable
from rdflib.namespace import RDF, XSD, SH
from rdflib.compare import isomorphic, graph_diff
from rdflib.term import Literal
import pandas

from namespace import MUST


@dataclass
class GraphComparison:
    in_expected_not_in_actual: Graph
    in_actual_not_in_expected: Graph
    in_both: Graph


@dataclass
class SpecResult:
    spec_uri: URIRef

    def __hash__(self):
        return hash(self.spec_uri)


@dataclass
class SpecPassed(SpecResult):
    def __init__(self, spec_uri):
        super(SpecPassed, self).__init__(spec_uri)


@dataclass
class SelectSpecFailure(SpecResult):
    table_comparison: pandas.DataFrame


@dataclass
class ConstructSpecFailure(SpecResult):
    graph_comparison: GraphComparison


@dataclass
class SparqlParseFailure(SpecResult):
    exception: ParseException


@dataclass
class SparqlAction:
    query: str


@dataclass
class SelectSparqlQuery(SparqlAction):
    def __init__(self, query):
        super(SelectSparqlQuery, self).__init__(query)


@dataclass
class ConstructSparqlQuery(SparqlAction):
    def __init__(self, query):
        super(ConstructSparqlQuery, self).__init__(query)


def run_specs(spec_path: Path) -> list[SpecResult]:
    ttl_files = list(spec_path.glob('**/*.ttl'))
    logging.info(f"Found {len(ttl_files)} ttl files")

    specs_graph = Graph()
    for file in ttl_files:
        specs_graph.parse(file)
    spec_uris = list(specs_graph.subjects(RDF.type, MUST.TestSpec))
    logging.info(f"Collected {len(spec_uris)} items")

    results = [run_spec(spec_uri, specs_graph) for spec_uri in spec_uris]

    return results


def run_spec(spec_uri, spec_graph) -> SpecResult:
    spec_uri = URIRef(str(spec_uri))
    given = get_given(spec_uri, spec_graph)
    when = get_when(spec_uri, spec_graph)
    when_type = type(when)
    when_bindings = get_when_bindings(spec_uri, spec_graph)
    result = None

    if when_type == SelectSparqlQuery:
        then = get_then_select(spec_uri, spec_graph)
        result = run_select_spec(spec_uri, given, when, then, when_bindings)
    elif when_type == ConstructSparqlQuery:
        then = get_then_construct(spec_uri, spec_graph)
        result = run_construct_spec(spec_uri, given, when, then, when_bindings)
    else:
        raise Exception(f"invalid spec when type {when_type}")

    return result


def run_select_spec(spec_uri: URIRef,
                    given: Graph,
                    when: SparqlAction,
                    then: pandas.DataFrame,
                    bindings: dict) -> SpecResult:
    logging.info(f"Running select spec {spec_uri}")

    try:
        result = given.query(when.query, initBindings=bindings)
        data_dict = {}
        columns = []
        series_list = []

        for item in result:
            for key, value in item.asdict().items():
                if key not in columns:
                    columns.append(key)
                    data_dict[key] = []
                    data_dict[key + "_datatype"] = []

        for item in result:
            for key, value in item.asdict().items():
                data_dict[key].append(value)
                if type(value) == Literal:
                    literal_type = XSD.string
                    if hasattr(value, "datatype") and value.datatype:
                        literal_type = value.datatype
                    data_dict[key + "_datatype"].append(literal_type)
                else:
                    data_dict[key + "_datatype"].append(XSD.anyURI)

        # convert dict to Series to avoid problem with array length
        for key, value in data_dict.items():
            series_list.append(pandas.Series(value, name=key))

        df = pandas.concat(series_list, axis=1)

        if "order by ?" or "order by desc" or "order by asc" not in when.query.lower():
            df.sort_values(by=columns[::2], inplace=True)
            df.reset_index(inplace=True, drop=True)
            # df.sort_index(axis=1, inplace=True)

        df_diff = then.compare(df, result_names=("expected", "actual"))

        if df_diff.empty:
            return SpecPassed(spec_uri)
        else:
            return SelectSpecFailure(spec_uri, df_diff)

    except ParseException as e:
        return SparqlParseFailure(spec_uri, e)


def run_construct_spec(spec_uri: URIRef,
                       given: Graph,
                       when: SparqlAction,
                       then: Graph,
                       bindings: dict) -> SpecResult:
    logging.info(f"Running construct spec {spec_uri}")
    result = given.query(when.query, initBindings=bindings).graph

    graph_compare = graph_comparison(then, result)
    equal = isomorphic(result, then)
    if equal:
        return SpecPassed(spec_uri)
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


def get_given(spec_uri: URIRef, spec_graph: Graph) -> Graph:
    given_query = f"""CONSTRUCT {{ ?s ?p ?o }} WHERE {{ <{spec_uri}> <{MUST.given}> [ a <{MUST.StatementsDataset}>; <{MUST.statements}> [ a <{RDF.Statement}> ; <{RDF.subject}> ?s ; <{RDF.predicate}> ?p ; <{RDF.object}> ?o ; ] ] }}"""
    initial_state = spec_graph.query(given_query).graph
    return initial_state


# Consider a SPARQL parser to determine query type https://github.com/cdhx/SPARQL_parse
def get_when(spec_uri: URIRef, spec_graph: Graph) -> SparqlAction:
    when_query = f"""SELECT ?type ?query {{ <{spec_uri}> <{MUST.when}> [ a ?type ; <{MUST.query}> ?query ; ] }}"""
    whens = spec_graph.query(when_query)
    for when in whens:
        if when.type == MUST.SelectSparql:
            return SelectSparqlQuery(when.query.value)
        elif when.type == MUST.ConstructSparql:
            return ConstructSparqlQuery(when.query.value)


def get_when_bindings(spec_uri: URIRef, spec_graph: Graph) -> dict:
    when_bindings_query = f"""SELECT ?variable ?binding {{ <{spec_uri}> <{MUST.when}> [ a ?type ; <{MUST.bindings}> [ <{MUST.variable}> ?variable ; <{MUST.binding}> ?binding ; ]  ] }}"""
    when_bindings = spec_graph.query(when_bindings_query)

    if len(when_bindings.bindings) == 0:
        return {}
    else:
        bindings = {}
        for binding in when_bindings:
            bindings[Variable(binding.variable.value)] = binding.binding
        return bindings


def get_then_construct(spec_uri: URIRef, spec_graph: Graph) -> Graph:
    then_query = f"""
    prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> 
    
    CONSTRUCT {{ ?s ?p ?o }}
    {{
        <{spec_uri}> <{MUST.then}> [
            a <{MUST.StatementsDataset}> ;
            <{MUST.statements}> [
                a rdf:Statement ;
                rdf:subject ?s ;
                rdf:predicate ?p ;
                rdf:object ?o ;
            ] ;
            ]
    }}
    """
    expected_results = spec_graph.query(then_query).graph

    return expected_results


def get_then_select(spec_uri: URIRef, spec_graph: Graph) -> pandas.DataFrame:
    then_query = f"""
    SELECT ?then ?order ?variable ?binding
    WHERE {{ 
        <{spec_uri}> <{MUST.then}> ?then .
        ?then a <{MUST.TableDataset}> ;
              <{MUST.rows}> [ <{SH.order}> 1 ;
                              <{MUST.row}> [
                                <{MUST.variable}> ?variable ;
                                <{MUST.binding}> ?binding ;
                                ] ; 
                            ] .
        }}"""

    expected_results = spec_graph.query(then_query)
    data_dict = {}
    columns = []
    series_list = []

    for then, items in groupby(expected_results, lambda er: er.then):
        for i in list(items):
            if i.variable.value not in columns:
                data_dict[i.variable.value] = []
                data_dict[i.variable.value + "_datatype"] = []

    for then, items in groupby(expected_results, lambda er: er.then):
        for i in list(items):
            data_dict[i.variable.value].append(i.binding)

            if type(i.binding) == Literal:
                literal_type = XSD.string
                if hasattr(i.binding, "datatype") and i.binding.datatype:
                    literal_type = i.binding.datatype
                data_dict[i.variable.value + "_datatype"].append(literal_type)
            else:
                data_dict[i.variable.value + "_datatype"].append(XSD.anyURI)

    # convert dict to Series to avoid problem with array length
    for key, value in data_dict.items():
        series_list.append(pandas.Series(value, name=key))

    df = pandas.concat(series_list, axis=1)

    return df
