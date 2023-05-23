import os

import tomli

import logger_setup
from dataclasses import dataclass

from pyparsing import ParseException
from pathlib import Path
from requests import ConnectionError, ConnectTimeout, HTTPError

from rdflib import Graph, URIRef, RDF, XSD

from rdflib.compare import isomorphic, graph_diff
import pandas
from multimethods import MultiMethod, Default

from namespace import MUST
import requests
import json
from pandas import DataFrame

from spec_component import SpecComponent, parse_spec_component
from triple_store_dispatch import execute_select_spec, execute_construct_spec, execute_update_spec
from utils import get_project_root
from colorama import Fore, Style

log = logger_setup.setup_logger(__name__)

requests.packages.urllib3.disable_warnings()
requests.packages.urllib3.util.ssl_.DEFAULT_CIPHERS += ':HIGH:!DH:!aNULL'


@dataclass
class Specification:
    spec_uri: URIRef
    triple_store: dict
    given: Graph
    when: SpecComponent
    then: SpecComponent


@dataclass
class GraphComparison:
    in_expected_not_in_actual: Graph
    in_actual_not_in_expected: Graph
    in_both: Graph


@dataclass
class SpecResult:
    spec_uri: URIRef
    triple_store: URIRef

    def __hash__(self):
        return hash(self.spec_uri, self.triple_store)


@dataclass
class SpecPassed(SpecResult):
    pass


@dataclass()
class SpecPassedWithWarning(SpecResult):
    warning: str


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
class SpecificationError(SpecResult):
    exception: ValueError


@dataclass
class TripleStoreConnectionError(SpecResult):
    exception: ConnectionError


@dataclass
class TestSkipped(SpecResult):
    message: str


@dataclass
class SparqlAction:
    query: str


@dataclass
class SelectSparqlQuery(SparqlAction):
    pass


@dataclass
class ConstructSparqlQuery(SparqlAction):
    pass


@dataclass
class UpdateSparqlQuery(SparqlAction):
    pass


# https://github.com/Semantic-partners/mustrd/issues/19
# https://github.com/Semantic-partners/mustrd/issues/103
def get_specs(spec_path: Path, triple_stores):
    # os.chdir(spec_path)
    ttl_files = list(spec_path.glob('*.ttl'))
    log.info(f"Found {len(ttl_files)} ttl files")

    spec_graph = Graph()
    subject_uris = set()
    results = []

    for file in ttl_files:
        log.info(f"Parse: {file}")
        file_graph = Graph().parse(file)
        for subject_uri in file_graph.subjects(RDF.type, MUST.TestSpec):
            error_messages = []
            query_types = file_graph.objects(predicate=MUST.queryType)
            result_types = [file_graph.objects(subject=then, predicate=RDF.type) for then in
                            file_graph.objects(subject_uri, MUST.then)]
            if subject_uri in subject_uris:
                log.warning(f"Duplicate subject URI found: {file.name} {subject_uri}. File will not be parsed.")
                error_messages += [f"Duplicate subject URI found in {file.name}."]

            if MUST.InheritedState in file_graph.objects(predicate=RDF.type) and \
                    MUST.UpdateSparql in file_graph.objects(predicate=MUST.queryType):
                log.warning(
                    f"An attempted update on an inherited state was found: {file.name}. {subject_uri} will not be parsed.")
                error_messages += [f"Attempted update on inherited state found in {file.name}."]

            if (MUST.SelectSparql in query_types) and (
                    MUST.EmptyGraphResult in result_types or MUST.StatementsDataSource in result_types):
                log.warning(
                    f"Incompatible when and then statements found: {file.name}. {subject_uri} will not be parsed.")
                error_messages += [f"Incompatible when and then statements found in {file.name}"]

            if (MUST.UpdateSparql in query_types) and (MUST.EmptyTableResult in result_types or MUST.TableDataSource in result_types):
                log.warning(
                    f"Incompatible when and then statements found: {file.name}. {subject_uri} will not be parsed.")
                error_messages += [f"Incompatible when and then statements foundin  {file.name}"]

        if len(error_messages) > 0:
            error_message = " ".join(msg for msg in error_messages)
            results += [TestSkipped(subject_uri, triple_store["type"], error_message) for triple_store in
                        triple_stores]
        else:
            subject_uris.add(subject_uri)
            spec_graph.parse(file)

    spec_uris = list(spec_graph.subjects(RDF.type, MUST.TestSpec))
    log.info(f"Collected {len(spec_uris)} items")
    return spec_uris, spec_graph, results


def run_specs(spec_uris, spec_graph, results, triple_stores, given_path: Path = None,
              when_path: Path = None, then_path: Path = None) -> list[SpecResult]:
    specs = []

    for triple_store in triple_stores:
        if "error" in triple_store:
            log.error(f"{triple_store['error']}. No specs run for this triple store.")
            results += [TestSkipped(spec_uri, triple_store['type'], triple_store['error']) for spec_uri in
                        spec_uris]
        else:
            for spec_uri in spec_uris:
                try:
                    specs = specs + [get_spec(spec_uri, spec_graph, given_path, when_path, then_path, triple_store)]
                except ValueError as e:
                    results += [SpecificationError(spec_uri, triple_store['type'], e)]
                except FileNotFoundError as e:
                    results += [SpecificationError(spec_uri, triple_store['type'], e)]

    log.info(f"Extracted {len(specs)} specifications")

    for specification in specs:
        results += [run_spec(specification)]

    return results


def get_spec(spec_uri: URIRef, spec_graph: Graph, given_path: Path = None, when_path: Path = None,
             then_path: Path = None, mustrd_triple_store: dict = None) -> Specification:
    try:
        if mustrd_triple_store is None:
            mustrd_triple_store = {"type": MUST.RdfLib}

        spec_uri = URIRef(str(spec_uri))

        given_component = parse_spec_component(subject=spec_uri,
                                               predicate=MUST.given,
                                               spec_graph=spec_graph,
                                               folder_location=given_path,
                                               mustrd_triple_store=mustrd_triple_store)

        log.debug(f"Given: {given_component.value}")

        when_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.when,
                                              spec_graph=spec_graph,
                                              folder_location=when_path,
                                              mustrd_triple_store=mustrd_triple_store)

        log.debug(f"when: {when_component.value}")

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              folder_location=then_path,
                                              mustrd_triple_store=mustrd_triple_store)

        log.debug(f"then: {then_component.value}")

        # https://github.com/Semantic-partners/mustrd/issues/92
        return Specification(spec_uri, mustrd_triple_store, given_component.value, when_component, then_component)
    except ValueError:
        raise
    except FileNotFoundError:
        raise


def run_spec(spec: Specification) -> SpecResult:
    spec_uri = spec.spec_uri
    triple_store = spec.triple_store
    # close_connection = True
    try:
        log.debug(f"run_when {spec_uri=}, {triple_store=}, {spec.given=}, {spec.when=}, {spec.then=}")
        return run_when(spec)

    except ParseException as e:
        log.error(f"{type(e)} {e}")
        return SparqlParseFailure(spec_uri, triple_store["type"], e)
    except (ConnectionError, TimeoutError, HTTPError, ConnectTimeout) as e:
        # close_connection = False
        template = "An exception of type {0} occurred. Arguments:\n{1!r}"
        message = template.format(type(e).__name__, e.args)
        log.error(message)
        return TripleStoreConnectionError(spec_uri, triple_store["type"], message)
    except TypeError as e:
        log.error(f"{type(e)} {e}")
        # https://github.com/Semantic-partners/mustrd/issues/97
        raise
    except Exception as e:
        log.error(f"{type(e)} {e}")
        return SparqlExecutionError(spec_uri, triple_store["type"], e)
    # https://github.com/Semantic-partners/mustrd/issues/78
    # finally:
    #     if type(mustrd_triple_store) == MustrdAnzo and close_connection:
    #         mustrd_triple_store.clear_graph()


def dispatch_run_when(spec: Specification):
    to = spec.when.queryType
    log.info(f"dispatch_run_when to SPARQL type {to}")
    return to


run_when = MultiMethod('run_when', dispatch_run_when)


@run_when.method(MUST.UpdateSparql)
def _multi_run_when_update(spec: Specification):
    # log.info(f" _multi_run_when_update(spec_uri, mustrd_triple_store, given, when_component, then_component):")

    then = spec.then.value

    result = run_update_spec(spec.spec_uri, spec.given, spec.when.value, then,
                             spec.triple_store, spec.when.bindings)

    return result


@run_when.method(MUST.ConstructSparql)
def _multi_run_when_construct(spec: Specification):
    # log.info(f" _multi_run_when_construct(spec_uri, mustrd_triple_store, given, when_component, then_component):")
    then = spec.then.value
    result = run_construct_spec(spec.spec_uri, spec.given, spec.when.value, then, spec.triple_store, spec.when.bindings)
    return result


@run_when.method(MUST.SelectSparql)
def _multi_run_when_select(spec: Specification):
    # log.info(f" _multi_run_when_select(spec_uri, mustrd_triple_store, given, when_component, then_component):")
    then = spec.then.value
    result = run_select_spec(spec.spec_uri, spec.given, spec.when.value, then, spec.triple_store, spec.then.ordered,
                             spec.when.bindings)
    return result


@run_when.method(Default)
def _multi_run_when_default(spec: Specification):
    raise Exception(f"invalid {spec.spec_uri=} when type {spec.when.queryType}")


def is_json(myjson: str) -> bool:
    try:
        json.loads(myjson)
    except ValueError:
        return False
    return True


def get_triple_stores(triple_store_graph: Graph) -> list:
    triple_stores = []
    for triple_store_config, rdf_type, triple_store_type in triple_store_graph.triples((None, RDF.type, None)):
        triple_store = {}
        # Local rdf lib triple store
        if triple_store_type == MUST.RdfLibConfig:
            triple_store["type"] = MUST.RdfLib
        # Anzo graph via anzo
        elif triple_store_type == MUST.AnzoConfig:
            triple_store["type"] = MUST.Anzo
            triple_store["url"] = triple_store_graph.value(subject=triple_store_config, predicate=MUST.url)
            triple_store["port"] = triple_store_graph.value(subject=triple_store_config, predicate=MUST.port)
            try:
                triple_store["username"] = get_credential_from_file(triple_store_config, "username",
                                                                    triple_store_graph.value(
                                                                        subject=triple_store_config,
                                                                        predicate=MUST.username))
                triple_store["password"] = get_credential_from_file(triple_store_config, "password",
                                                                    triple_store_graph.value(
                                                                        subject=triple_store_config,
                                                                        predicate=MUST.password))
            except (FileNotFoundError, ValueError) as e:
                triple_store["error"] = e
                # raise
            triple_store["gqe_uri"] = triple_store_graph.value(subject=triple_store_config, predicate=MUST.gqeURI)
            triple_store["input_graph"] = triple_store_graph.value(subject=triple_store_config,
                                                                   predicate=MUST.inputGraph)
            try:
                check_triple_store_params(triple_store, ["url", "port", "username", "password", "input_graph"])
            except ValueError as e:
                triple_store["error"] = e
        # GraphDB
        elif triple_store_type == MUST.GraphDbConfig:
            triple_store["type"] = MUST.GraphDb
            triple_store["url"] = triple_store_graph.value(subject=triple_store_config, predicate=MUST.url)
            triple_store["port"] = triple_store_graph.value(subject=triple_store_config, predicate=MUST.port)
            try:
                triple_store["username"] = get_credential_from_file(triple_store_config, "username",
                                                                    triple_store_graph.value(
                                                                        subject=triple_store_config,
                                                                        predicate=MUST.username))
                triple_store["password"] = get_credential_from_file(triple_store_config, "password",
                                                                    triple_store_graph.value(
                                                                        subject=triple_store_config,
                                                                        predicate=MUST.password))
            except (FileNotFoundError, ValueError) as e:
                triple_store["error"] = e
                # raise
            triple_store["repository"] = triple_store_graph.value(subject=triple_store_config,
                                                                  predicate=MUST.repository)
            triple_store["input_graph"] = triple_store_graph.value(subject=triple_store_config,
                                                                   predicate=MUST.inputGraph)

            try:
                check_triple_store_params(triple_store, ["url", "port", "repository"])
            except ValueError as e:
                triple_store["error"] = e
        else:
            triple_store["type"] = triple_store_type
            triple_store["error"] = f"Triple store not implemented: {triple_store_type}"

        triple_stores.append(triple_store)
    return triple_stores


def check_triple_store_params(triple_store, required_params):
    missing_params = [param for param in required_params if triple_store.get(param) is None]
    if missing_params:
        raise ValueError(f"Cannot establish connection to {triple_store['type']}. "
                         f"Missing required parameter(s): {', '.join(missing_params)}.")


def get_credential_from_file(triple_store_name, credential, config_path: str) -> str:
    if config_path is None:
        raise ValueError(f"Cannot establish connection defined in {triple_store_name}. "
                         f"Missing required parameter: {credential}.")
    project_root = get_project_root()
    path = Path(os.path.join(project_root, config_path))
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Credentials config file not found: {path}")
    try:
        with open(path, "rb") as f:
            config = tomli.load(f)
    except tomli.TOMLDecodeError as e:
        raise ValueError(f"Error reading credentials config file: {e}")
    return config[str(triple_store_name)][credential]


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


# https://github.com/Semantic-partners/mustrd/issues/110
# https://github.com/Semantic-partners/mustrd/issues/52
def run_select_spec(spec_uri: URIRef,
                    given: Graph,
                    when: str,
                    then: pandas.DataFrame,
                    triple_store: dict,
                    then_ordered: bool = False,
                    bindings: dict = None) -> SpecResult:
    log.info(f"Running select spec {spec_uri} on {triple_store['type']}")

    warning = None

    try:
        result = execute_select_spec(triple_store, given, when, bindings)
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
                return SpecPassedWithWarning(spec_uri, triple_store["type"], warning)
            else:
                return SpecPassed(spec_uri, triple_store["type"])
        else:
            log.error(message)
            return SelectSpecFailure(spec_uri, triple_store["type"], df_diff, message)

    except ParseException as e:
        return SparqlParseFailure(spec_uri, triple_store["type"], e)


def run_construct_spec(spec_uri: URIRef,
                       given: Graph,
                       when: str,
                       then: Graph,
                       triple_store: dict,
                       bindings: dict = None) -> SpecResult:
    log.info(f"Running construct spec {spec_uri} on {triple_store['type']}")

    try:
        result = execute_construct_spec(triple_store, given, when, bindings)
        # result = mustrd_triple_store.execute_construct(given, when, bindings)

        graph_compare = graph_comparison(then, result)
        equal = isomorphic(result, then)
        if equal:
            return SpecPassed(spec_uri, triple_store["type"])
        else:
            return ConstructSpecFailure(spec_uri, triple_store["type"], graph_compare)
    except ParseException as e:
        return SparqlParseFailure(spec_uri, triple_store["type"], e)


def run_update_spec(spec_uri: URIRef,
                    given: Graph,
                    when: str,
                    then: Graph,
                    triple_store: dict,
                    bindings: dict = None) -> SpecResult:
    log.info(f"Running update spec {spec_uri} on {triple_store['type']}")

    try:
        result = execute_update_spec(triple_store, given, when, bindings)

        graph_compare = graph_comparison(then, result)
        equal = isomorphic(result, then)
        if equal:
            return SpecPassed(spec_uri, triple_store["type"])
        else:
            return UpdateSpecFailure(spec_uri, triple_store["type"], graph_compare)

    except ParseException as e:
        return SparqlParseFailure(spec_uri, triple_store["type"], e)
    except NotImplementedError as ex:
        return TestSkipped(spec_uri, triple_store["type"], ex)


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
        <{spec_uri}> <{MUST.then}> 
            a <{MUST.StatementsDataSource}> ;
            <{MUST.statements}> [
                a rdf:Statement ;
                rdf:subject ?s ;
                rdf:predicate ?p ;
                rdf:object ?o ;
            ] ; ] 
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


def review_results(results, verbose):
    pass_count = 0
    warning_count = 0
    fail_count = 0
    skipped_count = 0
    print("===== Result Overview =====")
    for res in results:
        if type(res) == SpecPassed:
            colour = Fore.GREEN
            pass_count += 1
        elif type(res) == SpecPassedWithWarning:
            colour = Fore.YELLOW
            warning_count += 1
        elif type(res) == TestSkipped:
            colour = Fore.YELLOW
            skipped_count += 1
        else:
            colour = Fore.RED
            fail_count += 1
        print(f"{res.spec_uri} {res.triple_store} {colour}{type(res).__name__}{Style.RESET_ALL}")

    if fail_count or skipped_count:
        overview_colour = Fore.RED
    elif warning_count:
        overview_colour = Fore.YELLOW
    else:
        overview_colour = Fore.GREEN

    logger_setup.flush()
    print(f"{overview_colour}===== {fail_count} failures, {skipped_count} skipped, {Fore.GREEN}{pass_count} passed, "
          f"{overview_colour}{warning_count} passed with warnings =====")

    if verbose and (fail_count or warning_count or skipped_count):
        for res in results:
            if type(res) == SelectSpecFailure:
                print(f"{Fore.RED}Failed {res.spec_uri} {res.triple_store}")
                print(res.message)
                print(res.table_comparison.to_markdown())
            if type(res) == ConstructSpecFailure or type(res) == UpdateSpecFailure:
                print(f"{Fore.RED}Failed {res.spec_uri} {res.triple_store}")
            if type(res) == SpecPassedWithWarning:
                print(f"{Fore.YELLOW}Passed with warning {res.spec_uri} {res.triple_store}")
                print(res.warning)
            if type(res) == TripleStoreConnectionError or type(res) == SparqlExecutionError or \
                    type(res) == SparqlParseFailure or type(res) == SpecificationError:
                print(f"{Fore.RED}Failed {res.spec_uri} {res.triple_store}")
                print(res.exception)
            if type(res) == TestSkipped:
                print(f"{Fore.YELLOW}Skipped {res.spec_uri} {res.triple_store}")
                print(res.message)
