import logging
from dataclasses import dataclass
from pyparsing import ParseException
from itertools import groupby
from pathlib import Path

from rdflib import Graph, URIRef, Variable
from rdflib.namespace import RDF, XSD
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
    message: str


@dataclass
class ConstructSpecFailure(SpecResult):
    graph_comparison: GraphComparison


@dataclass
class UpdateSpecFailure(SpecResult):
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


@dataclass
class UpdateSparqlQuery(SparqlAction):
    def __init__(self, query):
        super(UpdateSparqlQuery, self).__init__(query)


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
        is_ordered = is_then_select_ordered(spec_uri, spec_graph)
        result = run_select_spec(spec_uri, given, when, then, when_bindings, is_ordered)
    elif when_type == ConstructSparqlQuery:
        then = get_then_construct(spec_uri, spec_graph)
        result = run_construct_spec(spec_uri, given, when, then, when_bindings)
    elif when_type == UpdateSparqlQuery:
        then = get_then_update(spec_uri, spec_graph)
        result = run_update_spec(spec_uri, given, when, then, when_bindings)
    else:
        raise Exception(f"invalid spec when type {when_type}")

    return result


def run_select_spec(spec_uri: URIRef,
                    given: Graph,
                    when: SparqlAction,
                    then: pandas.DataFrame,
                    bindings: dict = None,
                    ordered: bool = False) -> SpecResult:
    logging.info(f"Running select spec {spec_uri}")

    try:
        result = given.query(when.query, initBindings=bindings)
        series_list = []

        columns = get_select_columns(result)

        data_dict = populate_select_columns(columns, result)

        # convert dict to Series to avoid problem with array length
        for key, value in data_dict.items():
            series_list.append(pandas.Series(value, name=key))

        if series_list:
            df = pandas.concat(series_list, axis=1)
            when_ordered = False

            if "order by ?" not in when.query.lower() and "order by desc" not in when.query.lower() and "order by asc" not in when.query.lower():
                df.sort_values(by=columns[::2], inplace=True)

                df.reset_index(inplace=True, drop=True)
                if ordered:
                    logging.info(f"sh:order in {spec_uri} is ignored")
            else:
                when_ordered = True

            # Scenario 1: expected no result but got a result
            if then.empty:
                message = f"Expected 0 row(s) and 0 column(s), got {df.shape[0]} row(s) and {round(df.shape[1] / 2)} column(s)"
                then = create_empty_dataframe_with_columns(df)
                df_diff = then.compare(df, result_names=("expected", "actual"))
            else:
                # Scenario 2: expected a result and got a result
                message = f"Expected {then.shape[0]} row(s) and {round(then.shape[1] / 2)} column(s), " \
                          f"got {df.shape[0]} row(s) and {round(df.shape[1] / 2)} column(s)"
                if when_ordered is True and not ordered:
                    message += ". Actual result is ordered, must:then must contain sh:order on every row."
                    if df.shape == then.shape and (df.columns == then.columns).all():
                        df_diff = then.compare(df, result_names=("expected", "actual"))
                        if df_diff.empty:
                            df_diff = df
                    else:
                        df_diff = construct_df_diff(df, then)
                else:
                    if df.shape == then.shape and (df.columns == then.columns).all():
                        df_diff = then.compare(df, result_names=("expected", "actual"))
                    else:
                        df_diff = construct_df_diff(df, then)
        else:

            if then.empty:
                # Scenario 3: expected no result, got no result
                message = f"Expected 0 row(s) and 0 column(s), got 0 row(s) and 0 column(s)"
                df = pandas.DataFrame()
            else:
                # Scenario 4: expected a result, but got an empty result
                message = f"Expected {then.shape[0]} row(s) and {round(then.shape[1] / 2)} column(s), got 0 row(s) and 0 column(s)"
                df = create_empty_dataframe_with_columns(then)
            df_diff = then.compare(df, result_names=("expected", "actual"))

        if df_diff.empty:
            return SpecPassed(spec_uri)
        else:
            return SelectSpecFailure(spec_uri, df_diff, message)

    except ParseException as e:
        return SparqlParseFailure(spec_uri, e)


def run_construct_spec(spec_uri: URIRef,
                       given: Graph,
                       when: SparqlAction,
                       then: Graph,
                       bindings: dict = None) -> SpecResult:
    logging.info(f"Running construct spec {spec_uri}")

    try:
        result = given.query(when.query, initBindings=bindings).graph

        graph_compare = graph_comparison(then, result)
        equal = isomorphic(result, then)
        if equal:
            return SpecPassed(spec_uri)
        else:
            return ConstructSpecFailure(spec_uri, graph_compare)
    except ParseException as e:
        return SparqlParseFailure(spec_uri, e)


def run_update_spec(spec_uri: URIRef,
                    given: Graph,
                    when: SparqlAction,
                    then: Graph,
                    bindings: dict = None) -> SpecResult:
    logging.info(f"Running update spec {spec_uri}")

    try:
        result = given
        result.update(when.query, initBindings=bindings)

        graph_compare = graph_comparison(then, result)
        equal = isomorphic(result, then)
        if equal:
            return SpecPassed(spec_uri)
        else:
            return UpdateSpecFailure(spec_uri, graph_compare)

    except ParseException as e:
        return SparqlParseFailure(spec_uri, e)


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
        elif when.type == MUST.UpdateSparql:
            return UpdateSparqlQuery(when.query.value)


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


def is_then_select_ordered(spec_uri: URIRef, spec_graph: Graph) -> bool:
    ask_select_ordered = f"""
    ASK {{
    {{SELECT (count(?binding) as ?totalBindings) {{  
    <{spec_uri}> <{MUST.then}> ?then .
 	?then a <{MUST.TableDataset}> ;
       <{MUST.rows}> [ <{MUST.row}> [ <{MUST.variable}>  ?variable ;
                      <{MUST.binding}>  ?binding ;
                      ] ; ] .
}} }}
    {{SELECT (count(?binding) as ?orderedBindings) {{    
    <{spec_uri}> <{MUST.then}> ?then .
 	?then a <{MUST.TableDataset}> ;
       <{MUST.rows}> [ sh:order ?order ;
                    <{MUST.row}> [ <{MUST.variable}>  ?variable ;
                      <{MUST.binding}>  ?binding ;
                      ] ; ] .
}} }}
    FIlTER(?totalBindings = ?orderedBindings)
}}"""
    is_ordered = spec_graph.query(ask_select_ordered)
    return is_ordered.askAnswer


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


def get_then_update(spec_uri: URIRef, spec_graph: Graph) -> Graph:
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
    ask_empty_dataset = f"""
    ASK {{ <{spec_uri}> <{MUST.then}> ?then .
        ?then a <{MUST.EmptyResult}> }}"""
    empty_result = spec_graph.query(ask_empty_dataset)
    if empty_result.askAnswer is True:
        df = pandas.DataFrame()
        return df
    else:
        then_query = f"""
        SELECT ?then ?order ?variable ?binding
        WHERE {{ 
            <{spec_uri}> <{MUST.then}> ?then .
            ?then a <{MUST.TableDataset}> ;
                  <{MUST.rows}> [ <{MUST.row}> [
                                    <{MUST.variable}> ?variable ;
                                    <{MUST.binding}> ?binding ;
                                    ] ; 
                                ] .
            OPTIONAL {{ ?then <{MUST.rows}> [ sh:order ?order ;
                                            <{MUST.row}> [            
                                    <{MUST.variable}> ?variable ;
                                    <{MUST.binding}> ?binding ;
                                    ] ; 
                                ] . }}
            }} ORDER BY ASC(?order)"""

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


def calculate_row_difference(df1: pandas.DataFrame,
                             df2: pandas.DataFrame) -> pandas.DataFrame:
    df_all = df1.merge(df2.drop_duplicates(), how='left', indicator=True)
    actual_rows = df_all[df_all['_merge'] == 'left_only']
    actual_rows = actual_rows.drop('_merge', axis=1)
    return actual_rows


def construct_df_diff(df: pandas.DataFrame,
                      then: pandas.DataFrame) -> pandas.DataFrame:
    actual_rows = calculate_row_difference(df, then)
    expected_rows = calculate_row_difference(then, df)
    actual_columns = df.columns.difference(then.columns)
    expected_columns = then.columns.difference(df.columns)

    df_diff = pandas.DataFrame()
    modified_df = df
    modified_then = then

    if actual_columns.size > 0:
        modified_then = modified_then.reindex(modified_then.columns.to_list() + actual_columns.to_list(), axis=1)
        modified_then[actual_columns.to_list()] = modified_then[actual_columns.to_list()].fillna('')

    if expected_columns.size > 0:
        modified_df = modified_df.reindex(modified_df.columns.to_list() + expected_columns.to_list(), axis=1)
        modified_df[expected_columns.to_list()] = modified_df[expected_columns.to_list()].fillna('')

    modified_df = modified_df.reindex(modified_then.columns, axis=1)

    if df.shape[0] != then.shape[0] and df.shape[1] != then.shape[1]:
        # take modified columns and add rows
        actual_rows = calculate_row_difference(modified_df, modified_then)
        expected_rows = calculate_row_difference(modified_then, modified_df)
        df_diff = generate_row_diff(actual_rows, expected_rows)
    elif actual_rows.shape[0] > 0 or expected_rows.shape[0] > 0:
        df_diff = generate_row_diff(actual_rows, expected_rows)
    elif actual_columns.size > 0 or expected_columns.size > 0:
        df_diff = modified_then.compare(modified_df, result_names=("expected", "actual"), keep_shape=True,
                                        keep_equal=True)

    return df_diff


def generate_row_diff(actual_rows: pandas.DataFrame, expected_rows: pandas.DataFrame) -> pandas.DataFrame:
    df_diff_actual_rows = pandas.DataFrame()
    df_diff_expected_rows = pandas.DataFrame()

    if actual_rows.shape[0] > 0:
        empty_actual_copy = create_empty_dataframe_with_columns(actual_rows)
        df_diff_actual_rows = empty_actual_copy.compare(actual_rows, result_names=("expected", "actual"))

    if expected_rows.shape[0] > 0:
        empty_expected_copy = create_empty_dataframe_with_columns(expected_rows)
        df_diff_expected_rows = expected_rows.compare(empty_expected_copy, result_names=("expected", "actual"))

    df_diff_rows = pandas.concat([df_diff_actual_rows, df_diff_expected_rows], ignore_index=True)
    return df_diff_rows


def create_empty_dataframe_with_columns(original: pandas.DataFrame) -> pandas.DataFrame:
    empty_copy = original.copy()
    for col in empty_copy.columns:
        empty_copy[col].values[:] = None
    return empty_copy


def get_select_columns(result):
    columns = []
    for item in result:
        for key, value in item.asdict().items():
            if key not in columns:
                columns.append(key)
    return columns


def populate_select_columns(columns, result):
    data_dict = {}

    for column in columns:
        data_dict[column] = []
        data_dict[column + "_datatype"] = []

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
    return data_dict
