import os
from typing import Tuple, List, Union

import tomli
from rdflib.plugins.parsers.notation3 import BadSyntax

from . import logger_setup
from dataclasses import dataclass

from pyparsing import ParseException
from pathlib import Path
from requests import ConnectionError, ConnectTimeout, HTTPError, RequestException

from rdflib import Graph, URIRef, RDF, XSD, SH, Literal

from rdflib.compare import isomorphic, graph_diff
import pandas

from .namespace import MUST, TRIPLESTORE
import requests
import json
from pandas import DataFrame

from .spec_component import TableThenSpec, parse_spec_component, WhenSpec, ThenSpec
from .utils import is_json, get_mustrd_root
from colorama import Fore, Style
from tabulate import tabulate
from collections import defaultdict
from pyshacl import validate
import logging
from http.client import HTTPConnection
from .steprunner import upload_given, run_when_impl
from multimethods import MultiMethod
import traceback
from functools import wraps

log = logging.getLogger(__name__)

requests.packages.urllib3.disable_warnings()
requests.packages.urllib3.util.ssl_.DEFAULT_CIPHERS += ":HIGH:!DH:!aNULL"

logging.basicConfig(format="%(asctime)s %(message)s", level=logging.INFO)


def debug_requests_on():
    """Switches on logging of the requests module."""
    HTTPConnection.debuglevel = 1

    logging.basicConfig()
    logging.getLogger().setLevel(logging.DEBUG)
    requests_log = logging.getLogger("requests.packages.urllib3")
    requests_log.setLevel(logging.DEBUG)
    requests_log.propagate = True


def debug_requests_off():
    """Switches off logging of the requests module, might be some side-effects"""
    HTTPConnection.debuglevel = 0

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.WARNING)
    root_logger.handlers = []
    requests_log = logging.getLogger("requests.packages.urllib3")
    requests_log.setLevel(logging.WARNING)
    requests_log.propagate = False


debug_requests_off()


@dataclass(frozen=True)
class Specification:
    spec_uri: URIRef
    triple_store: dict
    given: Graph
    when: WhenSpec
    then: ThenSpec
    spec_file_name: str = "default.mustrd.ttl"
    spec_source_file: Path = Path("default.mustrd.ttl")


@dataclass
class GraphComparison:
    in_expected_not_in_actual: Graph
    in_actual_not_in_expected: Graph
    in_both: Graph


@dataclass
class SpecResult:
    spec_uri: URIRef
    triple_store: URIRef


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
class TripleStoreConnectionError(SpecResult):
    exception: ConnectionError


@dataclass
class SpecSkipped(SpecResult):
    message: str
    spec_file_name: str = "default.mustrd.ttl"
    spec_source_file: Path = Path("default.mustrd.ttl")


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
# Validate the specs found in spec_path
def validate_specs(
    run_config: dict,
    triple_stores: List,
    shacl_graph: Graph,
    ont_graph: Graph,
    file_name: str = "*",
    selected_test_files: List[str] = [],
) -> Tuple[List, Graph, List]:
    spec_graph = Graph()
    subject_uris = set()
    focus_uris = set()
    invalid_specs = []
    ttl_files = []

    if not selected_test_files:
        ttl_files = list(run_config["spec_path"].glob(f"**/{file_name}.mustrd.ttl"))
        log.info(
            f"Found {len(ttl_files)} {file_name}.mustrd.ttl files in {run_config['spec_path']}"
        )
    else:
        ttl_files = selected_test_files

    log.info(f"Using {ttl_files} for test source")
    ttl_files.sort()

    # For each spec file found in spec_path
    for file in ttl_files:
        # file = file.resolve()
        error_messages = []

        log.info(f"Parse: {file}")
        # Parse spec file and add error message if not conform to RDF standard
        try:
            file_graph = Graph().parse(file)
        except BadSyntax as e:
            template = "An exception of type {0} occurred when trying to parse a spec file. Arguments:\n{1!r}"
            message = template.format(type(e).__name__, e.args)
            log.error(message, exc_info=True)
            error_messages += [
                f"Could not extract spec from {file} due to exception of type "
                f"{type(e).__name__} when parsing file"
            ]
            continue

        # run shacl validation
        conforms, results_graph, results_text = validate(
            file_graph,
            shacl_graph=shacl_graph,
            ont_graph=ont_graph,
            inference="none",
            abort_on_first=False,
            allow_infos=False,
            allow_warnings=False,
            meta_shacl=False,
            advanced=True,
            js=False,
            debug=False,
        )
        if str(file.name).endswith("_duplicate"):
            log.debug(f"Validation of {file.name} against SHACL shapes: {conforms}")
            log.debug(f"{results_graph.serialize(format='turtle')}")
        # log.debug(f"SHACL validation results: {results_text}")
        # Add error message if not conform to spec shapes
        if not conforms:
            for msg in results_graph.objects(predicate=SH.resultMessage):
                log.warning(f"{file_graph}")
                log.warning(f"{msg} File: {file.name}")
                error_messages += [f"{msg} File: {file.name}"]

        # collect a list of uris of the tests in focus
        # If focus is found, only the spec in the focus will be executed
        for focus_uri in file_graph.subjects(
            predicate=MUST.focus, object=Literal("true", datatype=XSD.boolean)
        ):
            if focus_uri in focus_uris:
                focus_uri = URIRef(str(focus_uri) + "_DUPLICATE")
            focus_uris.add(focus_uri)

        add_spec_validation(
            file_graph,
            subject_uris,
            file,
            triple_stores,
            error_messages,
            invalid_specs,
            spec_graph,
        )

    valid_spec_uris = list(spec_graph.subjects(RDF.type, MUST.TestSpec))

    if focus_uris:
        invalid_focus_specs = get_invalid_focus_spec(focus_uris, invalid_specs)
        return focus_uris, spec_graph, invalid_focus_specs
    else:
        log.info(f"Collected {len(valid_spec_uris)} valid test spec(s)")
        return valid_spec_uris, spec_graph, invalid_specs


def get_invalid_focus_spec(focus_uris: set, invalid_specs: list):
    invalid_focus_specs = []
    for spec in invalid_specs:
        if spec.spec_uri in focus_uris:
            invalid_focus_specs += [spec]
            focus_uris.remove(spec.spec_uri)
    log.info(f"Collected {len(focus_uris)} focus test spec(s)")
    return invalid_focus_specs


# Detect duplicate,
# If no error: associate the spec configuration and the file where this conf is stored
# If error, aggregate the messages and mark spec as skipped
def add_spec_validation(
    file_graph: Graph,
    subject_uris: set,
    file: Path,
    triple_stores: List,
    error_messages: list,
    invalid_specs: list,
    spec_graph: Graph,
):

    for subject_uri in file_graph.subjects(RDF.type, MUST.TestSpec):
        # Always add file name and source file to the graph for error reporting
        file_graph.add([subject_uri, MUST.specSourceFile, Literal(str(file))])
        file_graph.add([subject_uri, MUST.specFileName, Literal(file.name)])

        # If we already collected a URI, then we tag it as duplicate and it won't be executed
        if subject_uri in subject_uris:
            log.warning(
                f"Duplicate subject URI found: {file.name} {subject_uri}. File will not be parsed."
            )
            error_messages += [f"Duplicate subject URI found in {file.name}."]
            subject_uri = URIRef(str(subject_uri) + "_DUPLICATE")
        if len(error_messages) == 0:
            subject_uris.add(subject_uri)
            this_spec_graph = Graph()
            this_spec_graph.parse(file)
            spec_uris_in_this_file = list(
                this_spec_graph.subjects(RDF.type, MUST.TestSpec)
            )
            for spec in spec_uris_in_this_file:
                this_spec_graph.add([spec, MUST.specSourceFile, Literal(file)])
                this_spec_graph.add([spec, MUST.specFileName, Literal(file.name)])
            spec_graph += this_spec_graph
        else:
            error_messages.sort()
            error_message = "\n".join(msg for msg in error_messages)
            invalid_specs += [
                SpecSkipped(
                    subject_uri, triple_store["type"], error_message, file.name, file
                )
                for triple_store in triple_stores
            ]


def get_specs(
    spec_uris: List[URIRef],
    spec_graph: Graph,
    triple_stores: List[dict],
    run_config: dict,
):
    specs = []
    skipped_results = []
    try:
        for triple_store in triple_stores:
            if "error" in triple_store:
                log.error(
                    f"{triple_store['error']}. No specs run for this triple store."
                )
                skipped_results += [
                    SpecSkipped(
                        spec_uri,
                        triple_store["type"],
                        triple_store["error"],
                        get_spec_file(spec_uri, spec_graph),
                    )
                    for spec_uri in spec_uris
                ]
            else:
                for spec_uri in spec_uris:
                    try:
                        specs += [
                            get_spec(spec_uri, spec_graph, run_config, triple_store)
                        ]
                    except (ValueError, FileNotFoundError, ConnectionError) as e:
                        # Try to get file name/path from the graph, but fallback to "unknown"
                        file_name = (
                            spec_graph.value(
                                subject=spec_uri, predicate=MUST.specFileName
                            )
                            or "unknown"
                        )
                        file_path = (
                            spec_graph.value(
                                subject=spec_uri, predicate=MUST.specSourceFile
                            )
                            or "unknown"
                        )
                        skipped_results += [
                            SpecSkipped(
                                spec_uri,
                                triple_store["type"],
                                str(e),
                                str(file_name),
                                Path(file_path),
                            )
                        ]

    except (BadSyntax, FileNotFoundError) as e:
        template = (
            "An exception of type {0} occurred when trying to parse the triple store configuration file. "
            "Arguments:\n{1!r}"
        )
        message = template.format(type(e).__name__, e.args)
        log.error(message)
        log.error("No specifications will be run.")

    log.info(f"Extracted {len(specs)} specifications that will be run")
    return specs, skipped_results


def run_specs(specs) -> List[SpecResult]:
    results = []
    # https://github.com/Semantic-partners/mustrd/issues/115
    for specification in specs:
        results.append(run_spec(specification))
    return results


def get_spec_file(spec_uri: URIRef, spec_graph: Graph):
    file_name = spec_graph.value(subject=spec_uri, predicate=MUST.specFileName)
    if file_name:
        return str(file_name)
    # fallback: try to get from MUST.specSourceFile
    file_path = spec_graph.value(subject=spec_uri, predicate=MUST.specSourceFile)
    if file_path:
        return str(Path(file_path).name)
    return "default.mustrd.ttl"


def get_spec(
    spec_uri: URIRef,
    spec_graph: Graph,
    run_config: dict,
    mustrd_triple_store: dict = None,
) -> Specification:
    try:
        if not mustrd_triple_store:
            mustrd_triple_store = {"type": TRIPLESTORE.RdfLib}
        components = []
        for predicate in MUST.given, MUST.when, MUST.then:
            components.append(
                parse_spec_component(
                    subject=spec_uri,
                    predicate=predicate,
                    spec_graph=spec_graph,
                    run_config=run_config,
                    mustrd_triple_store=mustrd_triple_store,
                )
            )

        spec_file_name = get_spec_file(spec_uri, spec_graph)
        spec_file_path = Path(
            spec_graph.value(
                subject=spec_uri,
                predicate=MUST.specSourceFile,
                default=Path("default.mustrd.ttl"),
            )
        )
        # https://github.com/Semantic-partners/mustrd/issues/92
        return Specification(
            spec_uri,
            mustrd_triple_store,
            components[0].value,
            components[1],
            components[2],
            spec_file_name,
            spec_file_path,
        )

    except (ValueError, FileNotFoundError) as e:
        template = (
            "An exception of type {0} occurred. Arguments:\n{1!r}\nStacktrace:\n{2}"
        )
        stacktrace = traceback.format_exc()
        message = template.format(type(e).__name__, e.args, stacktrace)
        log.exception(message)
        raise
    except ConnectionError as e:
        log.error(e)
        raise


def check_result(spec: Specification, result: Union[str, Graph]):

    log.debug(
        f"check_result {spec.spec_uri=}, {spec.triple_store=}, {result=} {type(spec.then)}"
    )
    if isinstance(spec.then, TableThenSpec):
        log.debug("table_comparison")
        return table_comparison(result, spec)
    else:
        graph_compare = graph_comparison(spec.then.value, result)
        if isomorphic(result, spec.then.value):
            log.debug(f"isomorphic {spec}")
            log.debug(f"{spec.spec_uri}")
            log.debug(f"{spec.triple_store}")
            ret = SpecPassed(spec.spec_uri, spec.triple_store["type"])

            return ret
        else:
            log.debug("not isomorphic")
            if spec.when[0].queryType == MUST.ConstructSparql:
                log.debug("ConstructSpecFailure")
                return ConstructSpecFailure(
                    spec.spec_uri, spec.triple_store["type"], graph_compare
                )
            else:
                log.debug("UpdateSpecFailure")
                return UpdateSpecFailure(
                    spec.spec_uri, spec.triple_store["type"], graph_compare
                )


def run_spec(spec: Specification) -> SpecResult:
    spec_uri = spec.spec_uri
    triple_store = spec.triple_store

    if not isinstance(spec, Specification):
        log.warning(f"check_result called with non-Specification: {type(spec)}")
        return spec
        # return SpecSkipped(getattr(spec, 'spec_uri', None), getattr(spec, 'triple_store', {}), "Spec is not a valid Specification instance")

    log.debug(f"run_spec {spec=}")
    log.debug(
        f"run_when {spec_uri=}, {triple_store=}, {spec.given=}, {spec.when=}, {spec.then=}"
    )
    if spec.given:
        given_as_turtle = spec.given.serialize(format="turtle")
        log.debug(f"{given_as_turtle}")
        upload_given(triple_store, spec.given)
    else:
        if triple_store["type"] == TRIPLESTORE.RdfLib:
            return SpecSkipped(
                spec_uri,
                triple_store["type"],
                "Unable to run Inherited State tests on Rdflib",
            )
    try:
        for when in spec.when:
            log.info(
                f"Running {when.queryType} spec {spec_uri} on {triple_store['type']}"
            )
            try:
                result = run_when_impl(spec_uri, triple_store, when)
                log.info(
                    f"run {when.queryType} spec {spec_uri} on {triple_store['type']} {result=}"
                )
            except ParseException as e:
                log.error(f"parseException {e}")
                return SparqlParseFailure(spec_uri, triple_store["type"], e)
            except NotImplementedError as ex:
                log.error(f"NotImplementedError {ex}")
                raise ex
                # return SpecSkipped(spec_uri, triple_store["type"], ex.args[0])
        return check_result(spec, result)
    except (ConnectionError, TimeoutError, HTTPError, ConnectTimeout, OSError) as e:
        # close_connection = False
        stacktrace = traceback.format_exc()
        template = "An exception of type {0} occurred. Arguments:\n{1!r}"
        message = template.format(type(e).__name__, e.args)
        log.error(message, exc_info=True)
        return TripleStoreConnectionError(spec_uri, triple_store["type"], message)
    except (TypeError, RequestException) as e:
        log.error(f"{type(e)} {e}", exc_info=True)
        return SparqlExecutionError(spec_uri, triple_store["type"], e)
    except Exception as e:
        log.error(f"Unexpected error {e}", exc_info=True)
        return RuntimeError(spec_uri, triple_store["type"], f"{type(e).__name__}: {e}")
    # https://github.com/Semantic-partners/mustrd/issues/78
    # finally:
    #     if type(mustrd_triple_store) == MustrdAnzo and close_connection:
    #         mustrd_triple_store.clear_graph()


def get_triple_store_graph(triple_store_graph_path: Path, secrets: str):
    graph = Graph()
    # Parse the main triple store graph file
    try:
        graph.parse(triple_store_graph_path)
    except Exception as e:
        log.error(f"Failed to parse triple store graph file '{triple_store_graph_path}': {e}")
        raise

    # Parse secrets, either from string or from file
    if secrets:
        log.info("Parsing secrets from provided string (--secrets option)")
        log.info("" + secrets)
        try:
            graph.parse(data=secrets)
        except Exception as e:
            log.error(f"Failed to parse secrets data for triple store graph: {e}")
            raise
    else:
        secret_path = triple_store_graph_path.with_name(
            triple_store_graph_path.stem + "_secrets" + triple_store_graph_path.suffix
        )
        log.info("Parsing secrets from secrets file: " + str(secret_path))
        if secret_path.exists():
            try:
                graph.parse(secret_path)
            except Exception as e:
                log.error(f"Failed to parse secrets file '{secret_path}': {e}")
                raise
        else:
            log.info(f"No secrets file found at '{secret_path}', continuing without it.")

    return graph


# Parse and validate triple store configuration
def get_triple_stores(triple_store_graph: Graph) -> list[dict]:
    triple_stores = []
    shacl_graph = Graph().parse(
        Path(os.path.join(get_mustrd_root(), "model/triplestoreshapes.ttl"))
    )
    ont_graph = Graph().parse(
        Path(os.path.join(get_mustrd_root(), "model/triplestoreOntology.ttl"))
    )
    # SHACL validation of triple store configuration
    conforms, results_graph, results_text = validate(
        data_graph=triple_store_graph,
        shacl_graph=shacl_graph,
        ont_graph=ont_graph,
        advanced=True,
        inference="none",
    )
    if not conforms:
        raise ValueError(
            f"Triple store configuration not conform to the shapes. SHACL report: {results_text}",
            results_graph,
        )
    for triple_store_config, rdf_type, triple_store_type in triple_store_graph.triples(
        (None, RDF.type, None)
    ):
        triple_store = {}
        triple_store["type"] = triple_store_type
        triple_store["uri"] = triple_store_config
        # Anzo graph via anzo
        if triple_store_type == TRIPLESTORE.Anzo:
            get_anzo_configuration(
                triple_store, triple_store_graph, triple_store_config
            )
        # GraphDB
        elif triple_store_type == TRIPLESTORE.GraphDb:
            get_graphDB_configuration(
                triple_store, triple_store_graph, triple_store_config
            )

        elif triple_store_type != TRIPLESTORE.RdfLib:
            triple_store["error"] = f"Triple store not implemented: {triple_store_type}"

        triple_stores.append(triple_store)
    return triple_stores


def get_anzo_configuration(
    triple_store: dict, triple_store_graph: Graph, triple_store_config: URIRef
):
    triple_store["url"] = triple_store_graph.value(
        subject=triple_store_config, predicate=TRIPLESTORE.url
    )
    triple_store["port"] = triple_store_graph.value(
        subject=triple_store_config, predicate=TRIPLESTORE.port
    )
    try:
        triple_store["username"] = str(
            triple_store_graph.value(
                subject=triple_store_config, predicate=TRIPLESTORE.username
            )
        )
        triple_store["password"] = str(
            triple_store_graph.value(
                subject=triple_store_config, predicate=TRIPLESTORE.password
            )
        )
    except (FileNotFoundError, ValueError) as e:
        triple_store["error"] = e
    triple_store["gqe_uri"] = triple_store_graph.value(
        subject=triple_store_config, predicate=TRIPLESTORE.gqeURI
    )
    triple_store["input_graph"] = triple_store_graph.value(
        subject=triple_store_config, predicate=TRIPLESTORE.inputGraph
    )
    triple_store["output_graph"] = triple_store_graph.value(
        subject=triple_store_config, predicate=TRIPLESTORE.outputGraph
    )
    try:
        check_triple_store_params(
            triple_store, ["url", "port", "username", "password", "input_graph"]
        )
    except ValueError as e:
        triple_store["error"] = e


def get_graphDB_configuration(
    triple_store: dict, triple_store_graph: Graph, triple_store_config: URIRef
):
    triple_store["url"] = triple_store_graph.value(
        subject=triple_store_config, predicate=TRIPLESTORE.url
    )
    triple_store["port"] = triple_store_graph.value(
        subject=triple_store_config, predicate=TRIPLESTORE.port
    )
    try:
        triple_store["username"] = str(
            triple_store_graph.value(
                subject=triple_store_config, predicate=TRIPLESTORE.username
            )
        )
        triple_store["password"] = str(
            triple_store_graph.value(
                subject=triple_store_config, predicate=TRIPLESTORE.password
            )
        )
    except (FileNotFoundError, ValueError) as e:
        log.error(f"Credential retrieval failed {e}")
        triple_store["error"] = e
    triple_store["repository"] = triple_store_graph.value(
        subject=triple_store_config, predicate=TRIPLESTORE.repository
    )
    triple_store["input_graph"] = triple_store_graph.value(
        subject=triple_store_config, predicate=TRIPLESTORE.inputGraph
    )
    try:
        check_triple_store_params(triple_store, ["url", "repository"])
    except ValueError as e:
        triple_store["error"] = e


def check_triple_store_params(triple_store: dict, required_params: List[str]):
    missing_params = [
        param for param in required_params if triple_store.get(param) is None
    ]
    if missing_params:
        raise ValueError(
            f"Cannot establish connection to {triple_store['type']}. "
            f"Missing required parameter(s): {', '.join(missing_params)}."
        )


def get_credential_from_file(
    triple_store_name: URIRef, credential: str, config_path: Literal
) -> str:
    log.info(
        f"get_credential_from_file {triple_store_name}, {credential}, {config_path}"
    )
    if not config_path:
        raise ValueError(
            f"Cannot establish connection defined in {triple_store_name}. "
            f"Missing required parameter: {credential}."
        )
    path = Path(config_path)
    log.info(f"get_credential_from_file {path}")

    if not os.path.isfile(path):
        log.error(f"couldn't find {path}")
        raise FileNotFoundError(f"Credentials config file not found: {path}")
    try:
        with open(path, "rb") as f:
            config = tomli.load(f)
    except tomli.TOMLDecodeError as e:
        log.error(f"config error {path} {e}")
        raise ValueError(f"Error reading credentials config file: {e}")
    return config[str(triple_store_name)][credential]


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

        frames = pandas.concat(
            objs=[frames, pandas.DataFrame([values], columns=columns)],
            ignore_index=True,
        )
        frames.fillna("", inplace=True)

        if frames.size == 0:
            frames = pandas.DataFrame()
    return frames


def table_comparison(result: str, spec: Specification) -> SpecResult:
    warning = None
    order_list = ["order by ?", "order by desc", "order by asc"]
    ordered_result = any(
        pattern in spec.when[0].value.lower() for pattern in order_list
    )

    # If sparql query doesn't contain order by clause, but order is define in then spec:
    # Then ignore order in then spec and print a warning
    if not ordered_result and spec.then.ordered:
        warning = f"sh:order in {spec.spec_uri} is ignored, no ORDER BY in query"
        log.warning(warning)

    # If sparql query contains an order by clause and then spec is not order:
    # Spec is inconsistent
    if ordered_result and not spec.then.ordered:
        message = (
            "Actual result is ordered, must:then must contain sh:order on every row."
        )
        return SelectSpecFailure(
            spec.spec_uri, spec.triple_store["type"], None, message
        )

    # Convert results to dataframe
    if is_json(result):
        df = json_results_to_panda_dataframe(result)
    else:
        return SelectSpecFailure(
            spec.spec_uri,
            spec.triple_store["type"],
            None,
            "Sparql result is not in JSON",
        )

    # Compare result with expected
    df_diff, message = compare_table_results(df, spec)

    if df_diff.empty:
        if warning:
            return SpecPassedWithWarning(
                spec.spec_uri, spec.triple_store["type"], warning
            )
        else:
            return SpecPassed(spec.spec_uri, spec.triple_store["type"])
    else:
        log.error("\n" + df_diff.to_markdown())
        log.error(message)
        return SelectSpecFailure(
            spec.spec_uri, spec.triple_store["type"], df_diff, message
        )


def compare_table_results_dispatch(resultDf: DataFrame, spec: Specification):
    return not resultDf.empty, not spec.then.value.empty


compare_table_results = MultiMethod(
    "compare_table_results", compare_table_results_dispatch
)


# Scenario 1: expected a result and got a result
@compare_table_results.method((True, True))
def _compare_results(resultDf: DataFrame, spec: Specification):
    columns = list(resultDf.columns)
    sorted_columns = sorted(columns)
    then = spec.then.value
    sorted_then_cols = sorted(list(then))
    order_list = ["order by ?", "order by desc", "order by asc"]
    ordered_result = any(
        pattern in spec.when[0].value.lower() for pattern in order_list
    )

    if not ordered_result:
        resultDf.sort_values(by=list(resultDf.columns)[::2], inplace=True)
        resultDf.reset_index(inplace=True, drop=True)

    if len(columns) == len(then.columns):
        if sorted_columns == sorted_then_cols:
            then = then[columns]
            if not ordered_result:
                then.sort_values(by=columns[::2], inplace=True)
                then.reset_index(drop=True, inplace=True)
            if (
                resultDf.shape == then.shape
                and (resultDf.columns == then.columns).all()
            ):
                df_diff = then.compare(resultDf, result_names=("expected", "actual"))
            else:
                df_diff = construct_df_diff(resultDf, then)
        else:
            then = then[sorted_then_cols]
            resultDf = resultDf[sorted_columns]
            df_diff = construct_df_diff(resultDf, then)
    else:
        then = then[sorted_then_cols]
        resultDf = resultDf[sorted_columns]
        df_diff = construct_df_diff(resultDf, then)

    message = build_summary_message(
        then.shape[0],
        round(then.shape[1] / 2),
        resultDf.shape[0],
        round(resultDf.shape[1] / 2),
    )
    return df_diff, message


# Scenario 2: expected no result but got a result
@compare_table_results.method((True, False))
def _unexpected_results(resultDf: DataFrame, spec: Specification):
    empty_then = create_empty_dataframe_with_columns(resultDf)
    df_diff = empty_then.compare(resultDf, result_names=("expected", "actual"))

    return df_diff, build_summary_message(
        0, 0, resultDf.shape[0], round(resultDf.shape[1] / 2)
    )


# Scenario 3: expected a result, but got an empty result
@compare_table_results.method((False, True))
def _missing_results(resultDf: DataFrame, spec: Specification):
    then = spec.then.value
    then = then[sorted(list(then))]
    df = create_empty_dataframe_with_columns(then)
    df_diff = then.compare(df, result_names=("expected", "actual"))

    return df_diff, build_summary_message(then.shape[0], round(then.shape[1] / 2), 0, 0)


# Scenario 4: expected no result, got no result
@compare_table_results.method((False, False))
def _no_results(resultDf: DataFrame, spec: Specification):
    df = pandas.DataFrame()
    df_diff = spec.then.value.compare(df, result_names=("expected", "actual"))

    return df_diff, build_summary_message(0, 0, 0, 0)


def build_summary_message(expected_rows, expected_columns, got_rows, got_columns):
    return (
        f"Expected {expected_rows} row(s) and {expected_columns} column(s), "
        f"got {got_rows} row(s) and {got_columns} column(s)"
    )


def graph_comparison(expected_graph: Graph, actual_graph: Graph) -> GraphComparison:
    diff = graph_diff(expected_graph, actual_graph)
    in_both = diff[0]
    in_expected = diff[1]
    in_actual = diff[2]
    in_expected_not_in_actual = in_expected - in_actual
    in_actual_not_in_expected = in_actual - in_expected
    return GraphComparison(
        in_expected_not_in_actual, in_actual_not_in_expected, in_both
    )


def get_then_update(spec_uri: URIRef, spec_graph: Graph) -> Graph:
    then_query = f"""
    prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

    CONSTRUCT {{ ?s ?p ?o }}
    {{
        <{spec_uri}> <{MUST.then}>
            a <{MUST.StatementsDataset}> ;
            <{MUST.hasStatement}> [
                a rdf:Statement ;
                rdf:subject ?s ;
                rdf:predicate ?p ;
                rdf:object ?o ;
            ] ; ]
    }}
    """
    expected_results = spec_graph.query(then_query).graph

    return expected_results


def write_result_diff_to_log(res, info):
    if isinstance(res, UpdateSpecFailure) or isinstance(res, ConstructSpecFailure):
        info(f"{Fore.RED}Failed {res.spec_uri} {res.triple_store}")
        info(f"{Fore.BLUE} In Expected Not In Actual:")
        info(res.graph_comparison.in_expected_not_in_actual.serialize(format="ttl"))
        info(f"{Fore.RED} in_actual_not_in_expected")
        info(res.graph_comparison.in_actual_not_in_expected.serialize(format="ttl"))
        info(f"{Fore.GREEN} in_both")
        info(res.graph_comparison.in_both.serialize(format="ttl"))

    if isinstance(res, SelectSpecFailure):
        info(f"{Fore.RED}Failed {res.spec_uri} {res.triple_store}")
        info(res.message)
        info(res.table_comparison.to_markdown())
    if isinstance(res, SpecPassedWithWarning):
        info(f"{Fore.YELLOW}Passed with warning {res.spec_uri} {res.triple_store}")
        info(res.warning)
    if (
        isinstance(res, TripleStoreConnectionError)
        or isinstance(res, SparqlExecutionError)
        or isinstance(res, SparqlParseFailure)
    ):
        info(f"{Fore.RED}Failed {res.spec_uri} {res.triple_store}")
        info(res.exception)
    if isinstance(res, SpecSkipped):
        info(f"{Fore.YELLOW}Skipped {res.spec_uri} {res.triple_store}")
        info(res.message)


def calculate_row_difference(
    df1: pandas.DataFrame, df2: pandas.DataFrame
) -> pandas.DataFrame:
    df_all = df1.merge(df2.drop_duplicates(), how="left", indicator=True)
    actual_rows = df_all[df_all["_merge"] == "left_only"]
    actual_rows = actual_rows.drop("_merge", axis=1)
    return actual_rows


def construct_df_diff(df: pandas.DataFrame, then: pandas.DataFrame) -> pandas.DataFrame:
    actual_rows = calculate_row_difference(df, then)
    expected_rows = calculate_row_difference(then, df)
    actual_columns = df.columns.difference(then.columns)
    expected_columns = then.columns.difference(df.columns)

    df_diff = pandas.DataFrame()
    modified_df = df
    modified_then = then

    if actual_columns.size > 0:
        modified_then = modified_then.reindex(
            modified_then.columns.to_list() + actual_columns.to_list(), axis=1
        )
        modified_then[actual_columns.to_list()] = modified_then[
            actual_columns.to_list()
        ].fillna("")

    if expected_columns.size > 0:
        modified_df = modified_df.reindex(
            modified_df.columns.to_list() + expected_columns.to_list(), axis=1
        )
        modified_df[expected_columns.to_list()] = modified_df[
            expected_columns.to_list()
        ].fillna("")

    modified_df = modified_df.reindex(modified_then.columns, axis=1)

    if df.shape[0] != then.shape[0] and df.shape[1] != then.shape[1]:
        # take modified columns and add rows
        actual_rows = calculate_row_difference(modified_df, modified_then)
        expected_rows = calculate_row_difference(modified_then, modified_df)
        df_diff = generate_row_diff(actual_rows, expected_rows)
    elif actual_rows.shape[0] > 0 or expected_rows.shape[0] > 0:
        df_diff = generate_row_diff(actual_rows, expected_rows)
    elif actual_columns.size > 0 or expected_columns.size > 0:
        df_diff = modified_then.compare(
            modified_df,
            result_names=("expected", "actual"),
            keep_shape=True,
            keep_equal=True,
        )
    df_diff.fillna("", inplace=True)
    return df_diff


def generate_row_diff(
    actual_rows: pandas.DataFrame, expected_rows: pandas.DataFrame
) -> pandas.DataFrame:
    df_diff_actual_rows = pandas.DataFrame()
    df_diff_expected_rows = pandas.DataFrame()

    if actual_rows.shape[0] > 0:
        empty_actual_copy = create_empty_dataframe_with_columns(actual_rows)
        df_diff_actual_rows = empty_actual_copy.compare(
            actual_rows, result_names=("expected", "actual")
        )

    if expected_rows.shape[0] > 0:
        empty_expected_copy = create_empty_dataframe_with_columns(expected_rows)
        df_diff_expected_rows = expected_rows.compare(
            empty_expected_copy, result_names=("expected", "actual")
        )

    df_diff_rows = pandas.concat(
        [df_diff_actual_rows, df_diff_expected_rows], ignore_index=True
    )
    return df_diff_rows


def create_empty_dataframe_with_columns(df: pandas.DataFrame) -> pandas.DataFrame:
    empty_copy = pandas.DataFrame().reindex_like(df)
    empty_copy.fillna("", inplace=True)
    return empty_copy


def review_results(results: List[SpecResult], verbose: bool) -> None:
    log.info("===== Result Overview =====")
    # Init dictionaries
    status_dict = defaultdict(lambda: defaultdict(int))
    status_counts = defaultdict(lambda: defaultdict(int))
    colours = {
        SpecPassed: Fore.GREEN,
        SpecPassedWithWarning: Fore.YELLOW,
        SpecSkipped: Fore.YELLOW,
    }
    # Populate dictionaries from results
    for result in results:
        status_counts[result.triple_store][type(result)] += 1
        status_dict[result.spec_uri][result.triple_store] = type(result)

    # Get the list of statuses and list of unique triple stores
    statuses = list(
        status for inner_dict in status_dict.values() for status in inner_dict.values()
    )
    triple_stores = list(
        set(
            status
            for inner_dict in status_dict.values()
            for status in inner_dict.keys()
        )
    )

    # Convert dictionaries to list for tabulate
    table_rows = [
        [spec_uri]
        + [
            f"""{colours.get(status_dict[spec_uri][triple_store], Fore.RED)}
        {status_dict[spec_uri][triple_store].__name__}{Style.RESET_ALL}"""
            for triple_store in triple_stores
        ]
        for spec_uri in set(status_dict.keys())
    ]

    status_rows = [
        [f"{colours.get(status, Fore.RED)}{status.__name__}{Style.RESET_ALL}"]
        + [
            f"{colours.get(status, Fore.RED)}{status_counts[triple_store][status]}{Style.RESET_ALL}"
            for triple_store in triple_stores
        ]
        for status in set(statuses)
    ]

    # Display tables with tabulate
    log.info(
        tabulate(
            table_rows,
            headers=["Spec Uris / triple stores"] + triple_stores,
            tablefmt="pretty",
        )
    )
    log.info(
        tabulate(
            status_rows,
            headers=["Status / triple stores"] + triple_stores,
            tablefmt="pretty",
        )
    )

    pass_count = statuses.count(SpecPassed)
    warning_count = statuses.count(SpecPassedWithWarning)
    skipped_count = statuses.count(SpecSkipped)
    fail_count = len(
        list(
            filter(
                lambda status: status
                not in [SpecPassed, SpecPassedWithWarning, SpecSkipped],
                statuses,
            )
        )
    )

    if fail_count:
        overview_colour = Fore.RED
    elif warning_count or skipped_count:
        overview_colour = Fore.YELLOW
    else:
        overview_colour = Fore.GREEN

    logger_setup.flush()
    log.info(
        f"{overview_colour}===== {fail_count} failures, {skipped_count} skipped, {Fore.GREEN}{pass_count} passed, "
        f"{overview_colour}{warning_count} passed with warnings ====="
    )

    if verbose and (fail_count or warning_count or skipped_count):
        display_verbose(results)


def display_verbose(results: List[SpecResult]):
    for res in results:
        if isinstance(res, UpdateSpecFailure):
            log.info(f"{Fore.RED}Failed {res.spec_uri} {res.triple_store}")
            log.info(f"{Fore.BLUE} In Expected Not In Actual:")
            log.info(
                res.graph_comparison.in_expected_not_in_actual.serialize(format="ttl")
            )
            log.info()
            log.info(f"{Fore.RED} in_actual_not_in_expected")
            log.info(
                res.graph_comparison.in_actual_not_in_expected.serialize(format="ttl")
            )
            log.info(f"{Fore.GREEN} in_both")
            log.info(res.graph_comparison.in_both.serialize(format="ttl"))

        if isinstance(res, SelectSpecFailure):
            log.info(f"{Fore.RED}Failed {res.spec_uri} {res.triple_store}")
            log.info(res.message)
            log.info(res.table_comparison.to_markdown())
        if isinstance(res, ConstructSpecFailure) or isinstance(res, UpdateSpecFailure):
            log.info(f"{Fore.RED}Failed {res.spec_uri} {res.triple_store}")
        if isinstance(res, SpecPassedWithWarning):
            log.info(
                f"{Fore.YELLOW}Passed with warning {res.spec_uri} {res.triple_store}"
            )
            log.info(res.warning)
        if (
            isinstance(res, TripleStoreConnectionError)
            or type(res, SparqlExecutionError)
            or isinstance(res, SparqlParseFailure)
        ):
            log.info(f"{Fore.RED}Failed {res.spec_uri} {res.triple_store}")
            log.info(res.exception)
        if isinstance(res, SpecSkipped):
            log.info(f"{Fore.YELLOW}Skipped {res.spec_uri} {res.triple_store}")
            log.info(res.message)


# Preserve the original run_when_impl multimethod
original_run_when_impl = run_when_impl


# Wrapper function for logging inputs and outputs of run_when
def run_when_with_logging(*args, **kwargs):
    log.debug(f"run_when called with args: {args}, kwargs: {kwargs}")
    result = original_run_when_impl(*args, **kwargs)  # Call the original multimethod
    log.debug(f"run_when returned: {result}")
    return result


# Replace the original run_when_impl with the wrapped version
run_when_impl = run_when_with_logging
run_when = run_when_impl
