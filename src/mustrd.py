import logging
from dataclasses import dataclass
from pyparsing import ParseException
from pathlib import Path

from rdflib import Graph, URIRef, Variable
from rdflib.namespace import RDF, XSD, SH
from rdflib.compare import isomorphic, graph_diff
import pandas

from namespace import MUST
from mustrdRdfLib import MustrdRdfLib
from mustrdAnzo import MustrdAnzo
import requests
import os
import io
import json
from pandas import DataFrame


logging.basicConfig(level=logging.INFO)
requests.packages.urllib3.disable_warnings()
requests.packages.urllib3.util.ssl_.DEFAULT_CIPHERS += ':HIGH:!DH:!aNULL'


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
class SpecComponent:
    value: str = None


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


# TODO figure out if **/* or *
def run_specs(spec_path: Path) -> list[SpecResult]:
    ttl_files = list(spec_path.glob('**/*.ttl'))
    # ttl_files = list(spec_path.glob('*.ttl'))
    logging.info(f"Found {len(ttl_files)} ttl files")

    specs_graph = Graph()
    for file in ttl_files:
        logging.info(f"Parse: {file}")
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
    elif when_type == UpdateSparqlQuery:
        then = get_then_update(spec_uri, spec_graph)
        result = run_update_spec(spec_uri, given, when, then, when_bindings)
    else:
        raise Exception(f"invalid spec when type {when_type}")

    return result


def run_triplestore_spec(spec_uri, spec_graph) -> SpecResult:
    spec_uri = URIRef(str(spec_uri))
    logging.info(f"\nRunning test: {spec_uri}")

    # Init triple store config
    mustrd_triple_store = get_triple_store(spec_graph, spec_uri)
    # Get GIVEN
    given = get_spec_component(subject=spec_uri,
                               predicate=MUST.hasGiven,
                               spec_graph=spec_graph,
                               mustrdTripleStore=mustrdTripleStore)

    logging.debug(f"Given: {given.value}")

    # Get WHEN
    when = get_spec_component(subject=spec_uri,
                              predicate=MUST.hasWhen,
                              spec_graph=spec_graph,
                              mustrdTripleStore=mustrdTripleStore)

    logging.debug(f"when: {when.value}")

    # Get THEN
    then = get_spec_component(subject=spec_uri,
                              predicate=MUST.hasThen,
                              spec_graph=spec_graph,
                              mustrdTripleStore=mustrdTripleStore)

    logging.debug(f"then: {then.value}")

    # Execute WHEN against GIVEN on the triple store
    execute_when(when, given, then, spec_uri, mustrd_triple_store)


def execute_when(when, given, then, spec_uri, mustrd_triple_store):
    try:
        if when.queryType == MUST.ConstructSparql:
            results = mustrdTripleStore.execute_construct(given=given.value,
                                                          when=when.value)
            thenGraph = Graph().parse(data=then.value)
            graph_compare = graph_comparison(thenGraph, results)
            equal = isomorphic(results, thenGraph)
            if equal:
                return SpecPassed(spec_uri)
            else:
                return ConstructSpecFailure(spec_uri, graph_compare)
        else:
            results = json_results_to_panda_dataframe(mustrdTripleStore.execute_select(given=given.value, when=when.value))
            then_frame = pandas.read_csv(io.StringIO(then.value))
            df_diff = then_frame.compare(results,
                                         result_names=("expected", "actual"))
            if df_diff.empty:
                return SpecPassed(spec_uri)
            else:
                return SelectSpecFailure(spec_uri, df_diff)
    except ParseException as e:
        return SparqlParseFailure(spec_uri, e)


def get_triple_store(spec_graph, spec_uri):
    triple_store_config = spec_graph.value(subject=spec_uri, predicate=MUST.tripleStoreConfig)
    triple_store_type = spec_graph.value(subject=triple_store_config, predicate=RDF.type)
    # Local rdf lib triple store
    if triple_store_type == MUST.rdfLibConfig:
        return MustrdRdfLib()
    # Anzo graph via anzo
    elif tripleStoreType == MUST.anzoConfig:
        anzoUrl = spec_graph.value(subject=tripleStoreConfig, predicate=MUST.anzoURL)
        anzoPort = spec_graph.value(subject=tripleStoreConfig, predicate=MUST.anzoPort)
        username = spec_graph.value(subject=tripleStoreConfig, predicate=MUST.anzoUser)
        password = spec_graph.value(subject=tripleStoreConfig, predicate=MUST.anzoPassword)
        gqeURI = spec_graph.value(subject=tripleStoreConfig, predicate=MUST.gqeURI)
        inputGraph = spec_graph.value(subject=tripleStoreConfig, predicate=MUST.inputGraph)
        return MustrdAnzo(anzoUrl=anzoUrl, anzoPort=anzoPort,
                          gqeURI=gqeURI, inputGraph=inputGraph,  username=username, password=password)
    else:
        raise Exception(f"Not Implemented {triple_store_type}")


def get_spec_component(subject, predicate, spec_graph, mustrd_triple_store):
    spec_component = SpecComponent()

    spec_component_node = spec_graph.value(subject=subject, predicate=predicate)
    if spec_component_node is None:
        raise Exception(f"specComponent Node empty for {subject} {predicate}")

    source_node = spec_graph.value(subject=spec_component_node, predicate=MUST.dataSource)
    if source_node is None:
        raise Exception(f"No data source for specComponent {subject} {predicate}")

    data_source_type = spec_graph.value(subject=source_node, predicate=RDF.type)
    if data_source_type is None:
        raise Exception(f"Node has no rdf type {subject} {predicate}")

    # Get specComponent from a file
    if data_source_type == MUST.FileDataSource:
        file_path = Path(spec_graph.value(subject=source_node, predicate=MUST.file))
        spec_component.value = get_spec_spec_component_from_file(file_path)
    # Get specComponent directly from config file (in text string)
    elif data_source_type == MUST.textDataSource:
        spec_component.value = spec_graph.value(subject=source_node, predicate=MUST.text)
    # Get specComponent with http GET protocol
    elif data_source_type == MUST.HttpDataSource:
        spec_component.value = requests.get(spec_graph.value(subject=source_node, predicate=MUST.dataSourceUrl)).content
    # From anzo specific source source
    elif type(mustrd_triple_store) == MustrdAnzo:
        # Get GIVEN or THEN from anzo graphmart
        if data_source_type == MUST.anzoGraphmartDataSource:
            graphmart = spec_graph.value(subject=source_node, predicate=MUST.graphmart)
            layer = spec_graph.value(subject=source_node, predicate=MUST.layer)
            spec_component.value = mustrd_triple_store.get_spec_component_from_graphmart(graphMart=graphmart, layer=layer)
        # Get WHEN specComponent from query builder
        elif data_source_type == MUST.anzoQueryBuilderDataSource:
            query_folder = spec_graph.value(subject=source_node, predicate=MUST.queryFolder)
            query_name = spec_graph.value(subject=source_node, predicate=MUST.queryName)
            spec_component.value = mustrd_triple_store.get_query_from_querybuilder(folderName=query_folder, queryName=query_name)
    # If anzo specific function is called but no anzo defined
    elif data_source_type == MUST.anzoGraphmartDataSource or data_source_type == MUST.anzoQueryBuilderDataSource:
        raise Exception(f"You must define {MUST.anzoConfig} to use {data_source_type}")
    else:
        raise Exception(f"Spec type not Implemented. specComponentNode: {source_node}. Type: {data_source_type}")

    if spec_graph.value(subject=spec_component_node, predicate=RDF.type) == MUST.when:
        spec_component.queryType = spec_graph.value(subject=spec_component_node, predicate=MUST.queryType)
    return spec_component


def get_spec_spec_component_from_file(path: Path):
    content = ""
    if os.path.isdir(path):
        for entry in path.iterdir():
            content += entry.read_text()
    else:
        content = path.read_text()
    return str(content)


# Convert sparql json query results as defined in https://www.w3.org/TR/rdf-sparql-json-res/
def json_results_to_panda_dataframe(result):
    json_result = json.loads(result)
    frames = DataFrame()
    for binding in json_result["results"]["bindings"]:
        columns = []
        values = []
        for key in binding:
            valueObject = binding[key]
            columns.append(key)
            values.append(valueObject["value"])
            columns.append(key + "_datatype")
            if "type" in valueObject and valueObject["type"] == "literal":
                literal_type = str(XSD.string)
                if "datatype" in valueObject:
                    literal_type = valueObject["datatype"]
                values.append(literal_type)
            else:
                values.append(str(XSD.anyURI))

        frames = pandas.concat(objs=[frames, pandas.DataFrame([values], columns=columns)], ignore_index=True)
    return frames


def run_select_spec(spec_uri: URIRef,
                    given: Graph,
                    when: SparqlAction,
                    then: pandas.DataFrame,
                    bindings: dict = None) -> SpecResult:
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

        if series_list:
            df = pandas.concat(series_list, axis=1)

            if "order by ?" or "order by desc" or "order by asc" not in when.query.lower():
                df.sort_values(by=columns[::2], inplace=True)
                df.reset_index(inplace=True, drop=True)

            # Scenario 1: expected no result but got a result
            if then.empty:
                message = f"Expected 0 row(s) and 0 column(s), got {df.shape[0]} row(s) and {round(df.shape[1] / 2)} column(s)"
                then = create_empty_dataframe_with_columns(df)
                df_diff = then.compare(df, result_names=("expected", "actual"))
            else:
                # Scenario 2: expected a result and got a result
                message = f"Expected {then.shape[0]} row(s) and {round(then.shape[1] / 2)} column(s), got {df.shape[0]} row(s) and {round(df.shape[1] / 2)} column(s)"
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
