import logger_setup
from dataclasses import dataclass

from pyparsing import ParseException
from pathlib import Path
from requests import ConnectionError, ConnectTimeout
from pathlib import PosixPath 
from rdflib import Graph, URIRef, RDF, XSD
import rdflib
from rdflib.compare import isomorphic, graph_diff
import pandas
import logging
from multimethods import MultiMethod, Default

from mustrdGraphDb import MustrdGraphDb
from namespace import MUST
from mustrdRdfLib import MustrdRdfLib
from mustrdAnzo import MustrdAnzo
import requests
import io
import json
from pandas import DataFrame

from spec_component import get_spec_component

log = logger_setup.setup_logger(__name__)

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
class SparqlExecutionError(SpecResult):
    exception: Exception


@dataclass
class TripleStoreConnectionError(SpecResult):
    exception: ConnectionError


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


# this is to demo the pattern, as it's one of the first ifs we have, 
# but we have so many, both as if, as case/switch, AND also delightfully 
# hidden behind a little OO polymorphism
# what the multi method enables is
# - extension in non centralised ways (like oo polymorphism, unlike switch)
# - re-use of the dispatch function for DIFFERENT methods (unlike OO polymorphism)
# - dispatch on arbitrarily complicated bits of data (unlike OO polymorphism, and most language switches)
def dispatch_runspecs(triplestore_spec_path, spec_graph, spec_uris):
    to = type(triplestore_spec_path)
    log.info(f"dispatch_runspecs dispatching {triplestore_spec_path=} {to=}")
    return to

run_specs_multi = MultiMethod('run_specs_multi', dispatch_runspecs)

@run_specs_multi.method(type(None))
def run_specs_against_rdflib(triplestore_spec_path, spec_graph, spec_uris):
    log.info("run_specs_against_rdflib")
    return [run_spec(spec_uri, spec_graph) for spec_uri in spec_uris]

@run_specs_multi.method(PosixPath)
def run_specs_against_triplestores(triplestore_spec_path, spec_graph, spec_uris):
    log.info("run_specs_against_triplestores")
    triple_store_config = Graph().parse(triplestore_spec_path)
    results = []
    for triple_store in get_triple_stores(triple_store_config):
        results = results + [run_spec(spec_uri, spec_graph, triple_store) for spec_uri in spec_uris]

    return results

@run_specs_multi.method(Default)
def run_specs_against_default(triplestore_spec_path, spec_graph, spec_uris):
    log.error(f"run_specs_against_default {triplestore_spec_path=} {spec_graph=}")
    raise Exception(f"didn't match anything with {triplestore_spec_path=}")


def dispatch_run_when(spec_uri, spec_graph, mustrd_triple_store, given, when_component, then_component):
    to = when_component.queryType
    log.info(f"dispatch_run_when {to}")
    return to

run_when = MultiMethod('run_when', dispatch_run_when)

# https://github.com/Semantic-partners/mustrd/issues/19
def run_specs(spec_path: Path, triplestore_spec_path: Path = None) -> list[SpecResult]:
    try: 
        # os.chdir(spec_path)
        ttl_files = list(spec_path.glob('*.ttl'))
        log.info(f"Found {len(ttl_files)} ttl files")

        spec_graph = Graph()
        for file in ttl_files:
            log.info(f"Parse: {file}")
            spec_graph.parse(file)
            filePath = str(file.absolute())
            log.error(f"{filePath=}")
            spec_graph.add((MUST.fileSource, MUST.loadedFromFile, rdflib.Literal(filePath)))
        spec_uris = list(spec_graph.subjects(RDF.type, MUST.TestSpec))
        log.info(f"Collected {len(spec_uris)} items")

        return run_specs_multi(triplestore_spec_path, spec_graph, spec_uris)
        # run in vanilla rdflib
        # if triplestore_spec_path is None:
        #     return run_specs_against_rdflib(spec_graph, spec_uris)
        # # run in triple stores
        # else:
        #     return run_specs_against_triplestores(triplestore_spec_path, spec_graph, spec_uris)  
    except Exception as e:
        # ensure we send enough info to caller to let it know what we were doing 
        raise Exception({
            'spec_path': spec_path.as_posix() if spec_path else None, 
            'triplestore_spec_path': triplestore_spec_path.as_posix() if triplestore_spec_path else None,
            'message': e.args}, e)


# https://github.com/Semantic-partners/mustrd/issues/58
# https://github.com/Semantic-partners/mustrd/issues/13
def run_spec(spec_uri, spec_graph, mustrd_triple_store=MustrdRdfLib()) -> SpecResult:
    close_connection = True
    spec_uri = URIRef(str(spec_uri))

    given_component = get_spec_component(subject=spec_uri,
                                         predicate=MUST.given,
                                         spec_graph=spec_graph,
                                         mustrd_triple_store=mustrd_triple_store)

    log.debug(f"Given: {given_component.value}")

    given = Graph().parse(data=given_component.value)

    when_component = get_spec_component(subject=spec_uri,
                                        predicate=MUST.when,
                                        spec_graph=spec_graph,
                                        mustrd_triple_store=mustrd_triple_store)

    log.debug(f"when: {when_component.value}")

    then_component = get_spec_component(subject=spec_uri,
                                        predicate=MUST.then,
                                        spec_graph=spec_graph,
                                        mustrd_triple_store=mustrd_triple_store)

    log.debug(f"then: {then_component.value}")

    try:
        log.info(f"run_when {spec_uri=}, {mustrd_triple_store=}, {given=}, {when_component=}, {then_component=}")
        return run_when(spec_uri, spec_graph, mustrd_triple_store, given, when_component, then_component)

    except ParseException as e:
        log.error(e)
        return SparqlParseFailure(spec_uri, e)
    except (ConnectionError, TimeoutError, ConnectTimeout) as e:
        close_connection = False
        template = "An exception of type {0} occurred. Arguments:\n{1!r}"
        message = template.format(type(e).__name__, e.args)
        log.error(message)
        return TripleStoreConnectionError(spec_uri, message)
    except TypeError as e:
        raise
    except Exception as e:
        log.error(f"{type(e)} {e}")
        return SparqlExecutionError(spec_uri, e)
    finally:
        if type(mustrd_triple_store) == MustrdAnzo and close_connection:
            mustrd_triple_store.clear_graph()


@run_when.method(MUST.UpdateSparql)
def _multi_run_when_update(spec_uri, spec_graph, mustrd_triple_store, given, when_component, then_component):
    log.info(f" _multi_run_when_update(spec_uri, mustrd_triple_store, given, when_component, then_component):")
    
    then = get_then_update(spec_uri, spec_graph)
    result = run_update_spec(spec_uri, given, when_component.value, then, when_component.bindings,
                                         mustrd_triple_store)
                             
    return result

@run_when.method(MUST.ConstructSparql)
def _multi_run_when_construct(spec_uri, spec_graph, mustrd_triple_store, given, when_component, then_component):
    log.info(f" _multi_run_when_construct(spec_uri, mustrd_triple_store, given, when_component, then_component):")

    then = Graph().parse(data=then_component.value)
    result = run_construct_spec(spec_uri, given, when_component.value, then, when_component.bindings,
                                            mustrd_triple_store)
    return result

@run_when.method(MUST.SelectSparql)
def _multi_run_when_select(spec_uri, spec_graph, mustrd_triple_store, given, when_component, then_component):
    log.info(f" _multi_run_when_select(spec_uri, mustrd_triple_store, given, when_component, then_component):")
    if type(then_component.value) == pandas.DataFrame:
        then = then_component.value
    else:
        then = pandas.read_csv(io.StringIO(then_component.value))
    result = run_select_spec(spec_uri, given, when_component.value, then, when_component.bindings,
                                         then_component.ordered, mustrd_triple_store)
    return result    

@run_when.method(Default)
def _multi_run_when_default(spec_uri, mustrd_triple_store, given, when_component, then_component):
    raise Exception(f"invalid {spec_uri=} when type {when_component.queryType}")

def is_json(myjson: str) -> bool:
    try:
        json.loads(myjson)
    except ValueError:
        return False
    return True

def get_triple_store_dispatch(tripleStoreType):
    return tripleStoreType

get_triple_store = MultiMethod("get_triple_store", get_triple_store_dispatch)

def get_triple_stores(triple_store_graph: Graph) -> list:
    triple_stores = []
    for tripleStoreConfig, type, tripleStoreType in triple_store_graph.triples((None, RDF.type, None)):
        log.info(f"get_triple_stores {tripleStoreConfig=}, {type=}, {tripleStoreType=}")
        triple_stores.append(get_triple_store(tripleStoreType, triple_store_graph, tripleStoreConfig))
    return triple_stores

@get_triple_store.method(MUST.rdfLibConfig)
def get_triplestore_graphdb(tripleStoreType, triple_store_graph, tripleStoreConfig):
    graph_db_url = triple_store_graph.value(subject=tripleStoreConfig, predicate=MUST.graphDbUrl)
    graph_db_port = triple_store_graph.value(subject=tripleStoreConfig, predicate=MUST.graphDbPort)
    username = triple_store_graph.value(subject=tripleStoreConfig, predicate=MUST.graphDbUser)
    password = triple_store_graph.value(subject=tripleStoreConfig, predicate=MUST.graphDbPassword)
    graph_db_repo = triple_store_graph.value(subject=tripleStoreConfig, predicate=MUST.graphDbRepo)
    input_graph = triple_store_graph.value(subject=tripleStoreConfig, predicate=MUST.inputGraph)
    return MustrdGraphDb(graphdb_url=graph_db_url, graphdb_port=graph_db_port,
                                               username=username, password=password, graphdb_repository=graph_db_repo,
                                               input_graph=input_graph)

@get_triple_store.method(MUST.anzoConfig)
def get_triplestore_anzo(tripleStoreType, triple_store_graph, triple_stores, tripleStoreConfig):
    anzo_url = triple_store_graph.value(subject=tripleStoreConfig, predicate=MUST.anzoURL)
    anzo_port = triple_store_graph.value(subject=tripleStoreConfig, predicate=MUST.anzoPort)
    username = triple_store_graph.value(subject=tripleStoreConfig, predicate=MUST.anzoUser)
    password = triple_store_graph.value(subject=tripleStoreConfig, predicate=MUST.anzoPassword)
    gqe_uri = triple_store_graph.value(subject=tripleStoreConfig, predicate=MUST.gqeURI)
    input_graph = triple_store_graph.value(subject=tripleStoreConfig, predicate=MUST.inputGraph)
    return MustrdAnzo(anzo_url=anzo_url, anzo_port=anzo_port,
                                            gqe_uri=gqe_uri, input_graph=input_graph, username=username,
                                            password=password)

@get_triple_store.method(MUST.graphDbConfig)
def _get_triplestore_rdflib(tripleStoreType, triple_store_graph, tripleStoreConfig):
    return MustrdRdfLib()


# Get column order
def json_results_order(result: str) -> list[str]:
    columns = []
    json_result = json.loads(result)
    for binding in json_result["head"]["vars"]:
        columns.append(binding)
        columns.append(binding + "_datatype")
    return columns


# Convert sparql json query results as defined in https://www.w3.org/TR/rdf-sparql-json-res/
def json_results_to_panda_dataframe(result: str) -> pandas.DataFrame:
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
        frames.fillna('', inplace=True)

        if frames.size == 0:
            frames = pandas.DataFrame()
    return frames


# https://github.com/Semantic-partners/mustrd/issues/52
def run_select_spec(spec_uri: URIRef,
                    given: Graph,
                    when: str,
                    then: pandas.DataFrame,
                    bindings: dict = None,
                    then_ordered: bool = False,
                    mustrd_triple_store=MustrdRdfLib()) -> SpecResult:
    log.info(f"Running select spec {spec_uri}")

    warning = None

    try:
        result = mustrd_triple_store.execute_select(given, when, bindings)
        if is_json(result):
            df = json_results_to_panda_dataframe(result)
            columns = json_results_order(result)
        else:
            raise ParseException

        if df.empty is False:
            when_ordered = False

            order_list = ["order by ?", "order by desc", "order by asc"]
            if any(pattern in when.lower() for pattern in order_list):
                when_ordered = True
            else:
                df = df[columns]
                df.sort_values(by=columns[::2], inplace=True)

                df.reset_index(inplace=True, drop=True)
                if then_ordered:
                    warning = f"sh:order in {spec_uri} is ignored, no ORDER BY in query"
                    log.warning(warning)

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
            log.error(message)
            return SelectSpecFailure(spec_uri, df_diff, message)

    except ParseException as e:
        return SparqlParseFailure(spec_uri, e)


def run_construct_spec(spec_uri: URIRef,
                       given: Graph,
                       when: str,
                       then: Graph,
                       bindings: dict = None,
                       mustrd_triple_store=MustrdRdfLib()) -> SpecResult:
    fileSource = list(given.objects(MUST.fileSource, MUST.loadedFromFile))
    log.info(f"Running construct spec {spec_uri} {fileSource=}")

    try:
        result = mustrd_triple_store.execute_construct(given, when, bindings)

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
                    bindings: dict = None,
                    mustrd_triple_store=MustrdRdfLib()) -> SpecResult:
    log.info(f"Running update spec {spec_uri}")

    try:
        result = mustrd_triple_store.execute_update(given, when, bindings)

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
