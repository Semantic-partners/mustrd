import logging
from dataclasses import dataclass
from typing import List
from pyparsing import ParseException
from itertools import groupby
from pathlib import Path

from rdflib import Graph, URIRef
from rdflib.namespace import RDF, XSD, SH
from rdflib.compare import isomorphic, graph_diff
from rdflib.term import Literal
import pandas

from namespace import MUST
from mustrdRdfLib import MustrdRdfLib
from mustrdAnzo import MustrdAnzo
import requests
import os
import csv
import io


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
class Spec_component:
    value: str = None


@dataclass
class SelectSparqlQuery(SparqlAction):
    def __init__(self, query):
        super(SelectSparqlQuery, self).__init__(query)


@dataclass
class ConstructSparqlQuery(SparqlAction):
    def __init__(self, query):
        super(ConstructSparqlQuery, self).__init__(query)


def run_specs(spec_path: Path) -> list[SpecResult]:
    ttl_files = list(spec_path.glob('*.ttl'))
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
    logging.info(f"\nRunning test: {spec_uri}")

    # Init triple store config
    mustrdTripleStore = get_triple_store(spec_graph, spec_uri)
    # Get GIVEN
    given = get_spec_component(subject=spec_uri, predicate=MUST.hasGiven, spec_graph=spec_graph, mustrdTripleStore=mustrdTripleStore)
    logging.info(f"Given: {given.value}")

    # Get WHEN
    when = get_spec_component(subject=spec_uri, predicate=MUST.hasWhen, spec_graph=spec_graph, mustrdTripleStore=mustrdTripleStore)
    logging.info(f"when: {when.value}")

    # Get THEN
    then = get_spec_component(subject=spec_uri, predicate=MUST.hasThen, spec_graph=spec_graph, mustrdTripleStore=mustrdTripleStore)
    logging.info(f"then: {then.value}")

    # Execute WHEN against GIVEN on the triple store
    execute_when(when, given, then, spec_uri, mustrdTripleStore)


def execute_when(when, given, then, spec_uri, mustrdTripleStore):
    try:
        if when.queryType == MUST.ConstructSparql:
            results = mustrdTripleStore.execute_construct(given=given.value, when=when.value)
            thenGraph = Graph().parse(data=then.value)
            graph_compare = graph_comparison(thenGraph, results)
            equal = isomorphic(results, thenGraph)
            if equal:
                return SpecPassed(spec_uri)
            else:
                return ConstructSpecFailure(spec_uri, graph_compare)
        else:
            results = mustrdTripleStore.execute_select(given=given.value, when=when.value)
            then_frame = format_csv_to_pandaFrame(csv.DictReader(io.StringIO(then.value)))
            df_diff = then_frame.compare(format_csv_to_pandaFrame(results), result_names=("expected", "actual"))
            if df_diff.empty:
                return SpecPassed(spec_uri)
            else:
                return SelectSpecFailure(spec_uri, df_diff)
    except ParseException as e:
        return SparqlParseFailure(spec_uri, e)


def get_triple_store(spec_graph, spec_uri):
    tripleStoreConfig = spec_graph.value(subject=spec_uri, predicate=MUST.tripleStoreConfig)
    tripleStoreType = spec_graph.value(subject=tripleStoreConfig, predicate=RDF.type)
    # Local rdf lib triple store
    if tripleStoreType == MUST.rdfLibConfig:
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
        raise Exception(f"Not Implemented {tripleStoreType}")


def get_spec_component(subject, predicate, spec_graph, mustrdTripleStore):
    specComponent = Spec_component()

    specComponentNode = spec_graph.value(subject=subject, predicate=predicate)
    if specComponentNode is None:
        raise Exception(f"specComponent Node empty for {subject} {predicate}")

    sourceNode = spec_graph.value(subject=specComponentNode, predicate=MUST.dataSource)
    if sourceNode is None:
        raise Exception(f"No data source for specComponent {subject} {predicate}")

    dataSourceType = spec_graph.value(subject=sourceNode, predicate=RDF.type)
    if dataSourceType is None:
        raise Exception(f"Node has no rdf type {subject} {predicate}")

    # Get specComponent from a file
    if dataSourceType == MUST.FileDataSource:
        filePath = Path(spec_graph.value(subject=sourceNode, predicate=MUST.file))
        specComponent.value = get_spec_specComponent_from_file(filePath)
    # Get specComponent directly from config file (in text string)
    elif dataSourceType == MUST.textDataSource:
        specComponent.value = spec_graph.value(subject=sourceNode, predicate=MUST.text)
    # Get specComponent with http GET protocol
    elif dataSourceType == MUST.HttpDataSource:
        specComponent.value = requests.get(spec_graph.value(subject=sourceNode, predicate=MUST.dataSourceUrl)).content
    # From anzo specific source source
    elif type(mustrdTripleStore) == MustrdAnzo:
        # Get GIVEN or THEN from anzo graphmart
        if dataSourceType == MUST.anzoGraphmartDataSource:
            graphMart = spec_graph.value(subject=sourceNode, predicate=MUST.graphmart)
            layer = spec_graph.value(subject=sourceNode, predicate=MUST.layer)
            specComponent.value = mustrdTripleStore.getSpecspecComponentGraphmart(graphMart=graphMart, layer=layer)
        # Get WHEN specComponent from query builder
        elif dataSourceType == MUST.anzoQueryBuilderDataSource:
            queryFolder = spec_graph.value(subject=sourceNode, predicate=MUST.queryFolder)
            queryName = spec_graph.value(subject=sourceNode, predicate=MUST.queryName)
            specComponent.value = mustrdTripleStore.getQueryFromQueryBuilder(folderName=queryFolder, queryName=queryName)
    # If anzo specific function is called but no anzo defined
    elif dataSourceType == MUST.anzoGraphmartDataSource or dataSourceType == MUST.anzoQueryBuilderDataSource:
        raise Exception(f"You must define {MUST.anzoConfig} to use {dataSourceType}")
    else:
        raise Exception(f"Spec type not Implemented. specComponentNode: {sourceNode}. Type: {dataSourceType}")

    if spec_graph.value(subject=specComponentNode, predicate=RDF.type) == MUST.when:
        specComponent.queryType = spec_graph.value(subject=specComponentNode, predicate=MUST.queryType)
    return specComponent


def get_spec_specComponent_from_file(path: Path):
    content = ""
    if os.path.isdir(path):
        for entry in path.iterdir():
            content += entry.read_text()
    else:
        content = path.read_text()
    return str(content)


def format_csv_to_pandaFrame(csv: List) -> pandas.DataFrame:

    frames = []
    for line in csv:
        columns = []
        values = []
        for key, value in line.items():
            columns.append(key)
            values.append(value)
            columns.append(key + "_datatype")
            if type(value) == Literal:
                literal_type = XSD.string
                if hasattr(value, "datatype") and value.datatype:
                    literal_type = value.datatype
                values.append(literal_type)
            else:
                values.append(XSD.anyURI)

        frames.append(pandas.DataFrame([values], columns=columns))

        return pandas.concat(frames, ignore_index=True)


def graph_comparison(expected_graph, actual_graph) -> GraphComparison:
    diff = graph_diff(expected_graph, actual_graph)
    in_both = diff[0]
    in_expected = diff[1]
    in_actual = diff[2]
    in_expected_not_in_actual = (in_expected - in_actual)
    in_actual_not_in_expected = (in_actual - in_expected)
    return GraphComparison(in_expected_not_in_actual, in_actual_not_in_expected, in_both)
