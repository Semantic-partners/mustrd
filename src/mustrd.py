import logging
from dataclasses import dataclass
from itertools import groupby

from pyparsing import ParseException
from pathlib import Path

from rdflib import Graph, URIRef, Literal, RDF, XSD

from rdflib.compare import isomorphic, graph_diff
import pandas

from mustrdGraphDb import MustrdGraphDb
from namespace import MUST
from mustrdRdfLib import MustrdRdfLib
from mustrdAnzo import MustrdAnzo
import requests
import io
import json
from pandas import DataFrame

from spec_component import get_spec_component

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


@dataclass()
class SpecPassedWithWarning(SpecResult):
    def __init__(self, spec_uri, warning):
        super().__init__(spec_uri)
        self.warning = warning


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


# https://github.com/Semantic-partners/mustrd/issues/19
def run_specs(spec_path: Path, triplestore_spec_path: Path = None) -> list[SpecResult]:
    # os.chdir(spec_path)
    ttl_files = list(spec_path.glob('*.ttl'))
    logging.info(f"Found {len(ttl_files)} ttl files")

    spec_graph = Graph()
    for file in ttl_files:
        logging.info(f"Parse: {file}")
        spec_graph.parse(file)
    spec_uris = list(spec_graph.subjects(RDF.type, MUST.TestSpec))
    logging.info(f"Collected {len(spec_uris)} items")

    results = []

    # run in vanilla rdflib
    if triplestore_spec_path is None:
        results += [run_spec(spec_uri, spec_graph) for spec_uri in spec_uris]
    # run in triple stores
    else:
        triple_store_config = Graph().parse(triplestore_spec_path)
        for triple_store in get_triple_stores(triple_store_config):
            results = results + [run_triplestore_spec(spec_uri, spec_graph, triple_store) for spec_uri in spec_uris]

    return results


def run_spec(spec_uri, spec_graph, mustrd_triple_store=MustrdRdfLib()) -> SpecResult:
    spec_uri = URIRef(str(spec_uri))

    given_component = get_spec_component(subject=spec_uri,
                                         predicate=MUST.given,
                                         spec_graph=spec_graph)

    logging.debug(f"Given: {given_component.value}")

    given = Graph().parse(data=given_component.value)

    when_component = get_spec_component(subject=spec_uri,
                                        predicate=MUST.when,
                                        spec_graph=spec_graph,
                                        mustrd_triple_store=mustrd_triple_store)

    logging.debug(f"when: {when_component.value}")

    then_component = get_spec_component(subject=spec_uri,
                                        predicate=MUST.then,
                                        spec_graph=spec_graph,
                                        mustrd_triple_store=mustrd_triple_store)

    logging.debug(f"then: {then_component.value}")

    result = None

    if when_component.queryType == MUST.SelectSparql:
        # when = SelectSparqlQuery(when_component.value)
        # then = get_then_select(spec_uri, spec_graph)
        # is_ordered = is_then_select_ordered(spec_uri, spec_graph)
        # result = execute_when(when_component, given_component, then_component, spec_uri, mustrd_triple_store)
        if type(then_component.value) == pandas.DataFrame:
            then = then_component.value
        elif is_json(then_component.value):
            then = json_results_to_panda_dataframe(then_component.value)
        else:
            then = pandas.read_csv(io.StringIO(then_component.value))
        result = run_select_spec(spec_uri, given_component.value, when_component.value, then, when_component.bindings,
                                 then_component.ordered, mustrd_triple_store)
    elif when_component.queryType == MUST.ConstructSparql:
        when = ConstructSparqlQuery(when_component.value)
        then = get_then_construct(spec_uri, spec_graph)
        result = run_construct_spec(spec_uri, given, when, then, when_component.bindings)
    elif when_component.queryType == MUST.UpdateSparql:
        when = UpdateSparqlQuery(when_component.value)
        then = get_then_update(spec_uri, spec_graph)
        result = run_update_spec(spec_uri, given, when, then, when_component.bindings)
    else:
        raise Exception(f"invalid spec when type {when_component.queryType}")

    return result


# https://github.com/Semantic-partners/mustrd/issues/65
def run_triplestore_spec(spec_uri, spec_graph, mustrd_triple_store=MustrdRdfLib()) -> SpecResult:
    spec_uri = URIRef(str(spec_uri))
    logging.info(f"\nRunning test: {spec_uri}")

    # Get GIVEN
    given = get_spec_component(subject=spec_uri,
                               predicate=MUST.given,
                               spec_graph=spec_graph,
                               mustrd_triple_store=mustrd_triple_store)

    logging.debug(f"Given: {given.value}")

    # Get WHEN
    when = get_spec_component(subject=spec_uri,
                              predicate=MUST.when,
                              spec_graph=spec_graph,
                              mustrd_triple_store=mustrd_triple_store)

    logging.debug(f"when: {when.value}")

    # Get THEN
    then = get_spec_component(subject=spec_uri,
                              predicate=MUST.then,
                              spec_graph=spec_graph,
                              mustrd_triple_store=mustrd_triple_store)

    logging.debug(f"then: {then.value}")

    # Execute WHEN against GIVEN on the triple store
    return execute_when(when, given, then, spec_uri, mustrd_triple_store)


# https://github.com/Semantic-partners/mustrd/issues/18
# https://github.com/Semantic-partners/mustrd/issues/38
def execute_when(when, given, then, spec_uri, mustrd_triple_store):
    try:
        if when.queryType == MUST.ConstructSparql:
            results = mustrd_triple_store.execute_construct(given=given.value,
                                                            when=when.value)
            then_graph = Graph().parse(data=then.value)
            graph_compare = graph_comparison(then_graph, results)
            equal = isomorphic(results, then_graph)
            if equal:
                return SpecPassed(spec_uri)
            else:
                return ConstructSpecFailure(spec_uri, graph_compare)
        elif when.queryType == MUST.SelectSparql:
            is_ordered = then.ordered
            results = json_results_to_panda_dataframe(
                mustrd_triple_store.execute_select(given=given.value, when=when.value, bindings=when.bindings))
            if type(then.value) == pandas.DataFrame:
                then_frame = then.value
            elif is_json(then.value):
                then_frame = json_results_to_panda_dataframe(then.value)
            else:
                then_frame = pandas.read_csv(io.StringIO(then.value))
            # Compare only compare with same number of rows
            if len(then_frame.index) != len(results.index):
                return SelectSpecFailure(spec_uri, then_frame.merge(results,
                                                                    indicator=True,
                                                                    how='outer'), message='Not the same number of rows')

            df_diff = then_frame.compare(results, result_names=("expected", "actual"))

            if df_diff.empty:
                return SpecPassed(spec_uri)
            else:
                logging.info(f"Test failed: spec_uri: {spec_uri}")
                return SelectSpecFailure(spec_uri, df_diff, message="Test failed")
        elif when.queryType == MUST.UpdateSparql:
            pass
        else:
            pass
    except ParseException as e:
        return SparqlParseFailure(spec_uri, e)


def is_json(myjson):
    try:
        json.loads(myjson)
    except ValueError as e:
        return False
    return True


def get_triple_stores(triple_store_graph):
    triple_stores = []
    for tripleStoreConfig, type, tripleStoreType in triple_store_graph.triples((None, RDF.type, None)):
        # Local rdf lib triple store
        if tripleStoreType == MUST.rdfLibConfig:
            triple_stores.append(MustrdRdfLib())
        # Anzo graph via anzo
        elif tripleStoreType == MUST.anzoConfig:
            anzo_url = triple_store_graph.value(subject=tripleStoreConfig, predicate=MUST.anzoURL)
            anzo_port = triple_store_graph.value(subject=tripleStoreConfig, predicate=MUST.anzoPort)
            username = triple_store_graph.value(subject=tripleStoreConfig, predicate=MUST.anzoUser)
            password = triple_store_graph.value(subject=tripleStoreConfig, predicate=MUST.anzoPassword)
            gqe_uri = triple_store_graph.value(subject=tripleStoreConfig, predicate=MUST.gqeURI)
            input_graph = triple_store_graph.value(subject=tripleStoreConfig, predicate=MUST.inputGraph)
            triple_stores.append(MustrdAnzo(anzoUrl=anzo_url, anzoPort=anzo_port,
                                            gqeURI=gqe_uri, inputGraph=input_graph, username=username,
                                            password=password))
        # GraphDB
        elif tripleStoreType == MUST.graphDbConfig:
            graph_db_url = triple_store_graph.value(subject=tripleStoreConfig, predicate=MUST.graphDbUrl)
            graph_db_port = triple_store_graph.value(subject=tripleStoreConfig, predicate=MUST.graphDbPort)
            username = triple_store_graph.value(subject=tripleStoreConfig, predicate=MUST.graphDbUser)
            password = triple_store_graph.value(subject=tripleStoreConfig, predicate=MUST.graphDbPassword)
            graph_db_repo = triple_store_graph.value(subject=tripleStoreConfig, predicate=MUST.graphDbRepo)
            input_graph = triple_store_graph.value(subject=tripleStoreConfig, predicate=MUST.inputGraph)
            triple_stores.append(MustrdGraphDb(graphDbUrl=graph_db_url, graphDbPort=graph_db_port,
                                               username=username, password=password, graphDbRepository=graph_db_repo,
                                               inputGraph=input_graph))
        else:
            raise Exception(f"Not Implemented {tripleStoreType}")
    return triple_stores




# Convert sparql json query results as defined in https://www.w3.org/TR/rdf-sparql-json-res/
def json_results_to_panda_dataframe(result):
    json_result = json.loads(result)
    frames = DataFrame()
    for binding in json_result["results"]["bindings"]:
        columns = []
        values = []
        for key in binding:
            value_object = binding[key]
            columns.append(key)
            values.append(str(value_object["value"]))
            columns.append(key + "_datatype")
            if "type" in value_object and value_object["type"] == "literal":
                literal_type = str(XSD.string)
                if "datatype" in value_object:
                    literal_type = value_object["datatype"]
                values.append(literal_type)
            else:
                values.append(str(XSD.anyURI))

        frames = pandas.concat(objs=[frames, pandas.DataFrame([values], columns=columns)], ignore_index=True)
        if frames.size == 0:
            frames = pandas.DataFrame()
    return frames


# https://github.com/Semantic-partners/mustrd/issues/52
def run_select_spec(spec_uri: URIRef,
                    given: str,
                    when: SparqlAction,
                    then: pandas.DataFrame,
                    bindings: dict = None,
                    then_ordered: bool = False,
                    mustrd_triple_store=MustrdRdfLib()) -> SpecResult:
    logging.info(f"Running select spec {spec_uri}")

    warning = None

    try:
        # result = given.query(when.query, initBindings=bindings)
        result = mustrd_triple_store.execute_select(given, when, bindings)
        series_list = []

        columns = get_select_columns(result)

        data_dict = populate_select_columns(columns, result)

        # convert dict to Series to avoid problem with array length
        for key, value in data_dict.items():
            series_list.append(pandas.Series(value, name=key))

        if series_list:
            df = pandas.concat(series_list, axis=1)
            when_ordered = False

            order_list = ["order by ?", "order by desc", "order by asc"]
            if any(pattern in when.lower() for pattern in order_list):
                when_ordered = True
            else:
                df.sort_values(by=columns[::2], inplace=True)

                df.reset_index(inplace=True, drop=True)
                if then_ordered:
                    warning = f"sh:order in {spec_uri} is ignored, no ORDER BY in query"
                    logging.info(warning)

            # Scenario 1: expected no result but got a result
            if then.empty:
                message = f"Expected 0 row(s) and 0 column(s), got {df.shape[0]} row(s) and {round(df.shape[1] / 2)} column(s)"
                then = create_empty_dataframe_with_columns(df)
                df_diff = then.compare(df, result_names=("expected", "actual"))
            else:
                # Scenario 2: expected a result and got a result
                message = f"Expected {then.shape[0]} row(s) and {round(then.shape[1] / 2)} column(s), " \
                          f"got {df.shape[0]} row(s) and {round(df.shape[1] / 2)} column(s)"
                if when_ordered is True and not then_ordered:
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
            if warning:
                return SpecPassedWithWarning(spec_uri, warning)
            else:
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


# https://github.com/Semantic-partners/mustrd/issues/12
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


def get_then_construct(spec_uri: URIRef, spec_graph: Graph) -> Graph:
    then_query = f"""
    prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> 

    CONSTRUCT {{ ?s ?p ?o }}
    {{
        <{spec_uri}> <{MUST.then}> [
        <{MUST.dataSource}> [
            a <{MUST.StatementsDataSource}> ;
            <{MUST.statements}> [
                a rdf:Statement ;
                rdf:subject ?s ;
                rdf:predicate ?p ;
                rdf:object ?o ;
            ] ; ] ; ]
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
        <{MUST.dataSource}> [
            a <{MUST.StatementsDataSource}> ;
            <{MUST.statements}> [
                a rdf:Statement ;
                rdf:subject ?s ;
                rdf:predicate ?p ;
                rdf:object ?o ;
            ] ; ] ; ]
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
            data_dict[key].append(str(value))
            if type(value) == Literal:
                literal_type = XSD.string
                if hasattr(value, "datatype") and value.datatype:
                    literal_type = value.datatype
                data_dict[key + "_datatype"].append(str(literal_type))
            else:
                data_dict[key + "_datatype"].append(str(XSD.anyURI))
    return data_dict
