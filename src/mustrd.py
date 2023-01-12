import logging
from dataclasses import dataclass
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
class Item:
    value:str = None

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
    # Init triple store config
    tripleStoreConfig = spec_graph.value(subject=spec_uri, predicate=MUST.tripleStoreConfig)
    mustrdTripleStore = None
    tripleStoreType = spec_graph.value(subject=tripleStoreConfig, predicate=RDF.type)
    # Local rdf lib triple store
    if  tripleStoreType == MUST.rdfLibConfig:
        mustrdTripleStore = MustrdRdfLib()
    # Anzo graph via anzo
    elif tripleStoreType == MUST.anzoConfig:
        anzoUrl = spec_graph.value(subject=tripleStoreConfig, predicate=MUST.anzoURL)
        anzoPort = spec_graph.value(subject=tripleStoreConfig, predicate=MUST.anzoPort)
        username = spec_graph.value(subject=tripleStoreConfig, predicate=MUST.anzoUser)
        password = spec_graph.value(subject=tripleStoreConfig, predicate=MUST.anzoPassword)
        gqeURI = spec_graph.value(subject=tripleStoreConfig, predicate=MUST.gqeURI)
        inputGraph = spec_graph.value(subject=tripleStoreConfig, predicate=MUST.inputGraph)
        mustrdTripleStore = MustrdAnzo(anzoUrl =anzoUrl, anzoPort=anzoPort,gqeURI=gqeURI,inputGraph=inputGraph,  username=username, password = password)
    else:
        raise Exception(f"Not Implemented {tripleStoreType}")    

    # Get GIVEN
    given = get_item(subject = spec_uri,predicate=MUST.hasGiven, spec_graph=spec_graph, mustrdTripleStore= mustrdTripleStore)
    logging.info(f"Given: {given.value}")
        
    # Get WHEN
    when = get_item(subject = spec_uri,predicate=MUST.hasWhen, spec_graph=spec_graph, mustrdTripleStore= mustrdTripleStore)
    logging.info(f"when: {when.value}")

    # Execute WHEN against GIVEN on the triple store
    result = mustrdTripleStore.executeWhenAgainstGiven(given=given,when=when)
    logging.info(f"result: {result}")

    # Get THEN
    then = get_item(subject = spec_uri,predicate=MUST.hasThen, spec_graph=spec_graph, mustrdTripleStore= mustrdTripleStore)
    logging.info(f"then: {then.value}")

    # Compare result with THEN

def get_item(subject, predicate, spec_graph, mustrdTripleStore):
    item = Item()
    
    itemNode=spec_graph.value(subject=subject, predicate=predicate)
    if itemNode==None: raise Exception(f"Item Node empty for {subject} {predicate}") 
    sourceNode = spec_graph.value(subject =itemNode, predicate=MUST.dataSource)
    if sourceNode==None: raise Exception(f"No data source for item {subject} {predicate}") 

    dataSourceType = spec_graph.value(subject=sourceNode, predicate=RDF.type)
    if dataSourceType==None: raise Exception(f"Node has no rdf type {subject} {predicate}") 

    # Get item from a file
    if dataSourceType == MUST.FileDataSource:
        filePath = Path(spec_graph.value(subject=sourceNode, predicate=MUST.file))
        item.value = getSpecItemFromFile(filePath)
    # Get item directly from config file (in text string)
    elif dataSourceType==MUST.textDataSource:
        item.value =  spec_graph.value(subject=sourceNode, predicate=MUST.text)
    # Get item with http GET protocol
    elif dataSourceType==MUST.HttpDataSource:
        item.value =  requests.get(spec_graph.value(subject=sourceNode, predicate=MUST.dataSourceUrl)).content
    # From anzo specific source source
    elif type(mustrdTripleStore) == MustrdAnzo:
        # Get GIVEN or THEN from anzo graphmart
        if dataSourceType==MUST.anzoGraphmartDataSource:
            graphMart = spec_graph.value(subject=sourceNode, predicate=MUST.graphmart)
            layer = spec_graph.value(subject=sourceNode, predicate=MUST.layer)
            item.value =  mustrdTripleStore.getSpecItemGraphmart(graphMart=graphMart,layer=layer)
        # Get WHEN item from query builder
        elif dataSourceType==MUST.anzoQueryBuilderDataSource:
            queryFolder = spec_graph.value(subject=sourceNode, predicate=MUST.queryFolder)
            queryName = spec_graph.value(subject=sourceNode, predicate=MUST.queryName)
            item.value =  mustrdTripleStore.getQueryFromQueryBuilder(folderName = queryFolder, queryName = queryName)
    # If anzo specific function is called but no anzo defined
    elif dataSourceType==MUST.anzoGraphmartDataSource or dataSourceType==MUST.anzoQueryBuilderDataSource:
        raise Exception(f"You must define {MUST.anzoConfig} to use {dataSourceType}")    
    else:
        raise Exception(f"Spec type not Implemented. itemNode: {sourceNode}. Type: {dataSourceType}") 
    return item

def getSpecItemFromFile(path: Path):
    content = ""
    if(os.path.isdir(path)):
        for entry in path.iterdir():
            content+=entry.read_text()
    else:
        content=path.read_text()
    return str(content)

def run_select_spec(spec_uri: URIRef,
                    given: Graph,
                    when: SparqlAction,
                    then: pandas.DataFrame) -> SpecResult:
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
                columns.append(key + "_datatype")
                if type(value) == Literal:
                    literal_type = XSD.string
                    if hasattr(value, "datatype")  and value.datatype:
                        literal_type = value.datatype
                    values.append(literal_type)
                else:
                    values.append(XSD.anyURI)

            frames.append(pandas.DataFrame([values], columns=columns))

            df = pandas.concat(frames, ignore_index=True)
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
                       then: Graph) -> SpecResult:
    logging.info(f"Running construct spec {spec_uri}")
    result = given.query(when.query).graph

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

    frames = []
    for then, items in groupby(expected_results, lambda er: er.then):
        columns = []
        values = []
        for i in list(items):
            columns.append(i.variable.value)
            values.append(i.binding)
            columns.append(i.variable.value + "_datatype")
            if type(i.binding) == Literal:
                literal_type = XSD.string
                if hasattr(i.binding, "datatype") and i.binding.datatype:
                    literal_type = i.binding.datatype
                values.append(literal_type)
            else:
                values.append(XSD.anyURI)
        frames.append(pandas.DataFrame([values], columns=columns))

    df = pandas.concat(frames, ignore_index=True)
    return df
