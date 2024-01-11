"""
MIT License

Copyright (c) 2023 Semantic Partners Ltd

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import os
from dataclasses import dataclass, field
from itertools import groupby
from pathlib import Path
from typing import Tuple, List, Type

import pandas
import requests
from rdflib import RDF, Graph, URIRef, Variable, Literal, XSD, util
from rdflib.exceptions import ParserError
from rdflib.term import Node
import logging 

import logger_setup
from mustrdAnzo import get_queries_for_layer, get_queries_from_templated_step, get_spec_component_from_graphmart, get_query_from_querybuilder, get_query_from_step
from namespace import MUST
from utils import get_project_root
from multimethods import MultiMethod, Default

log = logger_setup.setup_logger(__name__)


@dataclass
class SpecComponent:
    pass


@dataclass
class GivenSpec(SpecComponent):
    value: Graph = None


@dataclass
class WhenSpec(SpecComponent):
    value: str = None
    queryType: URIRef = None
    bindings: dict = None

@dataclass
class AnzoWhenSpec(WhenSpec):
    paramQuery: str = None
    queryTemplate: str = None

@dataclass
class ThenSpec(SpecComponent):
    value: Graph = Graph()
    ordered: bool = False


@dataclass
class TableThenSpec(ThenSpec):
    value: pandas.DataFrame = field(default_factory=pandas.DataFrame)


@dataclass
class SpecComponentDetails:
    subject: URIRef
    predicate: URIRef
    spec_graph: Graph
    mustrd_triple_store: dict
    spec_component_node: Node
    data_source_type: Node
    run_config: dict

def get_path(path_type: str, run_config: dict) -> Path:
    try:
        if str(run_config[path_type]).startswith("/"):
            return run_config[path_type]
        else: 
            return Path(os.path.join(run_config['spec_path'], run_config[path_type]))
    except(KeyError):
        if str(run_config['data_path']).startswith("/"):
            return run_config['data_path']
        else: 
            return Path(os.path.join(run_config['spec_path'], run_config['data_path']))
    

def parse_spec_component(subject: URIRef,
                         predicate: URIRef,
                         spec_graph: Graph,
                         run_config: dict,
                         mustrd_triple_store: dict) -> GivenSpec | WhenSpec | ThenSpec | TableThenSpec:
    spec_component_nodes = get_spec_component_nodes(subject, predicate, spec_graph)
    # all_data_source_types = []
    spec_components = []
    for spec_component_node in spec_component_nodes:
        data_source_types = get_data_source_types(subject, predicate, spec_graph, spec_component_node)
        for data_source_type in data_source_types:
            spec_component_details = SpecComponentDetails(
                subject=subject,
                predicate=predicate,
                spec_graph=spec_graph,
                mustrd_triple_store=mustrd_triple_store,
                spec_component_node=spec_component_node,
                data_source_type=data_source_type,
                run_config=run_config)
            spec_component = get_spec_component(spec_component_details)
            if type(spec_component) == list:
                spec_components += spec_component 
            else:
                spec_components += [spec_component]

        # all_data_source_types.extend(data_source_types)
    # return all_data_source_types
    # merge multiple graphs into one, give error if spec config is a TableThen
    return combine_specs(spec_components)


def get_spec_component_type(spec_components: List[SpecComponent]) -> Type[SpecComponent]:
    # Get the type of the first object in the list
    spec_type = type(spec_components[0])
    # Loop through the remaining objects in the list and check their types
    for spec_component in spec_components[1:]:
        if type(spec_component) != spec_type:
            # If an object has a different type, raise an error
            raise ValueError("All spec components must be of the same type")

    # If all objects have the same type, return the type
    return spec_type


def combine_specs_dispatch(spec_components: List[SpecComponent]) -> Type[SpecComponent]:
    spec_type = get_spec_component_type(spec_components)
    return spec_type


combine_specs = MultiMethod("combine_specs", combine_specs_dispatch)


@combine_specs.method(GivenSpec)
def _combine_given_specs(spec_components: List[GivenSpec]) -> GivenSpec:
    if len(spec_components) == 1:
        return spec_components[0]
    else:
        graph = Graph()
        for spec_component in spec_components:
            graph += spec_component.value
        given_spec = GivenSpec()
        given_spec.value = graph
        return given_spec


@combine_specs.method(WhenSpec)
def _combine_when_specs(spec_components: List[WhenSpec]) -> WhenSpec:
    return spec_components


@combine_specs.method(ThenSpec)
def _combine_then_specs(spec_components: List[ThenSpec]) -> ThenSpec:
    if len(spec_components) == 1:
        return spec_components[0]
    else:
        graph = Graph()
        for spec_component in spec_components:
            graph += spec_component.value
        then_spec = ThenSpec()
        then_spec.value = graph
        return then_spec


@combine_specs.method(TableThenSpec)
def _combine_table_then_specs(spec_components: List[TableThenSpec]) -> TableThenSpec:
    if len(spec_components) != 1:
        raise ValueError(f"Parsing of multiple components of MUST.then for tables not implemented")
    return spec_components[0]


@combine_specs.method(Default)
def _combine_specs_default(spec_components: List[SpecComponent]):
    raise ValueError(f"Parsing of multiple components of this type not implemented")

def get_data_source_types(subject: URIRef, predicate: URIRef, spec_graph: Graph, source_node: Node) -> List[Node]:
    data_source_types = []
    for data_source_type in spec_graph.objects(subject=source_node, predicate=RDF.type):
        data_source_types.append(data_source_type)
    # data_source_type = spec_graph.value(subject=source_node, predicate=RDF.type)
    if len(data_source_types) == 0:
        raise ValueError(f"Node has no rdf type {subject} {predicate}")
    return data_source_types

# https://github.com/Semantic-partners/mustrd/issues/99
def get_spec_component_dispatch(spec_component_details: SpecComponentDetails) -> Tuple[Node, URIRef]:
    return spec_component_details.data_source_type, spec_component_details.predicate


get_spec_component = MultiMethod("get_spec_component", get_spec_component_dispatch)


@get_spec_component.method((MUST.InheritedDataset, MUST.given))
def _get_spec_component_inheritedstate_given(spec_component_details: SpecComponentDetails) -> GivenSpec:
    spec_component = init_spec_component(spec_component_details.predicate)
    return spec_component


@get_spec_component.method((MUST.FolderDataset, MUST.given))
def _get_spec_component_folderdatasource_given(spec_component_details: SpecComponentDetails) -> GivenSpec:
    spec_component = init_spec_component(spec_component_details.predicate)

    file_name = spec_component_details.spec_graph.value(subject=spec_component_details.spec_component_node,
                                                        predicate=MUST.fileName)

    path = Path(os.path.join(str(get_path('given_path',spec_component_details.run_config)), str(file_name)))
    try:
        spec_component.value = Graph().parse(data=get_spec_component_from_file(path))
    except ParserError as e:
        log.error(f"Problem parsing {path}, error of type {type(e)}")
        raise ValueError(f"Problem parsing {path}, error of type {type(e)}")
    return spec_component


@get_spec_component.method((MUST.FolderSparqlSource, MUST.when))
def _get_spec_component_foldersparqlsource_when(spec_component_details: SpecComponentDetails) -> GivenSpec:
    spec_component = init_spec_component(spec_component_details.predicate)

    file_name = spec_component_details.spec_graph.value(subject=spec_component_details.spec_component_node,
                                                        predicate=MUST.fileName)

    path = Path(os.path.join(str(get_path('when_path',spec_component_details.run_config)), str(file_name)))
    spec_component.value = get_spec_component_from_file(path)
    spec_component.queryType = spec_component_details.spec_graph.value(subject=spec_component_details.spec_component_node,
                                                                       predicate=MUST.queryType)
    return spec_component


@get_spec_component.method((MUST.FolderDataset, MUST.then))
def _get_spec_component_folderdatasource_then(spec_component_details: SpecComponentDetails) -> ThenSpec:
    spec_component = init_spec_component(spec_component_details.predicate)

    file_name = spec_component_details.spec_graph.value(subject=spec_component_details.spec_component_node,
                                                        predicate=MUST.fileName)
    path = Path(os.path.join(str(get_path('then_path',spec_component_details.run_config)), str(file_name)))

    return get_then_from_file(path, spec_component)


def get_then_from_file(path: Path, spec_component: ThenSpec) -> ThenSpec:
    if path.is_dir():
        raise ValueError(f"Path {path} is a directory, expected a file")

    # https://github.com/Semantic-partners/mustrd/issues/94
    if path.suffix in {".csv", ".xlsx", ".xls"}:
        df = pandas.read_csv(path) if path.suffix == ".csv" else pandas.read_excel(path)
        then_spec = TableThenSpec()
        then_spec.value = df
        return then_spec
    else:
        try:
            file_format = util.guess_format(str(path))
        except AttributeError:
            raise ValueError(f"Unsupported file format: {path.suffix}")

        if file_format is not None:
            g = Graph()
            try:
                g.parse(data=get_spec_component_from_file(path), format=file_format)
            except ParserError as e:
                log.error(f"Problem parsing {path}, error of type {type(e)}")
                raise ValueError(f"Problem parsing {path}, error of type {type(e)}")
            spec_component.value = g
            return spec_component


@get_spec_component.method((MUST.FileDataset, MUST.given))
def _get_spec_component_filedatasource_given(spec_component_details: SpecComponentDetails) -> GivenSpec:
    spec_component = init_spec_component(spec_component_details.predicate)

    file_path = Path(str(spec_component_details.spec_graph.value(subject=spec_component_details.spec_component_node,
                                                                 predicate=MUST.file)))
    if str(file_path).startswith("/"): # absolute path
        path = file_path
    else: #relative path
        path = Path(os.path.join(spec_component_details.run_config['spec_path'], file_path))
    try:
        spec_component.value = Graph().parse(data=get_spec_component_from_file(path))
    except ParserError as e:
        log.error(f"Problem parsing {path}, error of type {type(e)}")
        raise ValueError(f"Problem parsing {path}, error of type {type(e)}")
    return spec_component


@get_spec_component.method((MUST.FileSparqlSource, MUST.when))
def _get_spec_component_filedatasource_when(spec_component_details: SpecComponentDetails) -> SpecComponent:
    spec_component = init_spec_component(spec_component_details.predicate)

    file_path = Path(str(spec_component_details.spec_graph.value(subject=spec_component_details.spec_component_node,
                                                                 predicate=MUST.file)))
    if str(file_path).startswith("/"): # absolute path
        path = file_path
    else: #relative path
        path = Path(os.path.join(spec_component_details.run_config['spec_path'], file_path))
    spec_component.value = get_spec_component_from_file(path)

    spec_component.queryType = spec_component_details.spec_graph.value(subject=spec_component_details.spec_component_node,
                                                                       predicate=MUST.queryType)

    return spec_component


@get_spec_component.method((MUST.FileDataset, MUST.then))
def _get_spec_component_filedatasource_then(spec_component_details: SpecComponentDetails) -> SpecComponent:
    spec_component = init_spec_component(spec_component_details.predicate)

    file_path = Path(str(spec_component_details.spec_graph.value(subject=spec_component_details.spec_component_node,
                                                                 predicate=MUST.file)))
    if str(file_path).startswith("/"): # absolute path
        path = file_path
    else: #relative path
        path = Path(os.path.join(spec_component_details.run_config['spec_path'], file_path))
    return get_then_from_file(path, spec_component)


@get_spec_component.method((MUST.TextSparqlSource, MUST.when))
def _get_spec_component_TextSparqlSource(spec_component_details: SpecComponentDetails) -> SpecComponent:
    spec_component = init_spec_component(spec_component_details.predicate)

    # Get specComponent directly from config file (in text string)
    spec_component.value = str(
        spec_component_details.spec_graph.value(subject=spec_component_details.spec_component_node,
                                                predicate=MUST.queryText))

    spec_component.bindings = get_when_bindings(spec_component_details.subject, spec_component_details.spec_graph)
    spec_component.queryType = spec_component_details.spec_graph.value(subject=spec_component_details.spec_component_node,
                                                                       predicate=MUST.queryType)
    return spec_component


# https://github.com/Semantic-partners/mustrd/issues/98
@get_spec_component.method((MUST.HttpDataset, MUST.given))
@get_spec_component.method((MUST.HttpDataset, MUST.when))
@get_spec_component.method((MUST.HttpDataset, MUST.then))
def _get_spec_component_HttpDataset(spec_component_details: SpecComponentDetails) -> SpecComponent:
    spec_component = init_spec_component(spec_component_details.predicate)

    # Get specComponent with http GET protocol
    spec_component.value = requests.get(str(
        spec_component_details.spec_graph.value(subject=spec_component_details.spec_component_node,
                                                predicate=MUST.dataSourceUrl)).content)    
    spec_component.queryType = spec_component_details.spec_graph.value(subject=spec_component_details.spec_component_node,
                                                                       predicate=MUST.queryType)
    return spec_component


@get_spec_component.method((MUST.TableDataset, MUST.then))
def _get_spec_component_TableDataset(spec_component_details: SpecComponentDetails) -> SpecComponent:
    table_then = TableThenSpec()
    # get specComponent from ttl table
    table_then.value = get_spec_from_table(spec_component_details.subject, spec_component_details.predicate,
                                           spec_component_details.spec_graph)
    table_then.ordered = is_then_select_ordered(spec_component_details.subject, spec_component_details.predicate,
                                                spec_component_details.spec_graph)
    return table_then


@get_spec_component.method((MUST.EmptyTable, MUST.then))
def _get_spec_component_EmptyTable(spec_component_details: SpecComponentDetails) -> SpecComponent:
    spec_component = TableThenSpec()
    return spec_component


@get_spec_component.method((MUST.EmptyGraph, MUST.then))
def _get_spec_component_EmptyGraph(spec_component_details: SpecComponentDetails) -> SpecComponent:
    spec_component = init_spec_component(spec_component_details.predicate)

    return spec_component


@get_spec_component.method((MUST.StatementsDataset, MUST.given))
@get_spec_component.method((MUST.StatementsDataset, MUST.then))
def _get_spec_component_StatementsDataset(spec_component_details: SpecComponentDetails) -> SpecComponent:
    spec_component = init_spec_component(spec_component_details.predicate)

    spec_component.value = Graph().parse(
        data=get_spec_from_statements(spec_component_details.subject, spec_component_details.predicate,
                                      spec_component_details.spec_graph))
    return spec_component


@get_spec_component.method((MUST.AnzoGraphmartDataset, MUST.given))
@get_spec_component.method((MUST.AnzoGraphmartDataset, MUST.then))
def _get_spec_component_AnzoGraphmartDataset(spec_component_details: SpecComponentDetails) -> SpecComponent:
    spec_component = init_spec_component(spec_component_details.predicate)

    if spec_component_details.mustrd_triple_store["type"] == MUST.Anzo:
        # Get GIVEN or THEN from anzo graphmart
        graphmart = spec_component_details.spec_graph.value(subject=spec_component_details.spec_component_node,
                                                            predicate=MUST.graphmart)
        layer = spec_component_details.spec_graph.value(subject=spec_component_details.spec_component_node,
                                                        predicate=MUST.layer)
        spec_component.value = get_spec_component_from_graphmart(
            triple_store=spec_component_details.mustrd_triple_store,
            graphmart=graphmart,
            layer=layer)
    else:
        raise ValueError(f"You must define {MUST.AnzoConfig} to use {MUST.AnzoGraphmartDataset}")

    return spec_component


@get_spec_component.method((MUST.AnzoQueryBuilderSparqlSource, MUST.when))
def _get_spec_component_AnzoQueryBuilderSparqlSource(spec_component_details: SpecComponentDetails) -> SpecComponent:
    spec_component = init_spec_component(spec_component_details.predicate)

    # Get WHEN specComponent from query builder
    if spec_component_details.mustrd_triple_store["type"] == MUST.Anzo:
        query_folder = spec_component_details.spec_graph.value(subject=spec_component_details.spec_component_node,
                                                               predicate=MUST.queryFolder)
        query_name = spec_component_details.spec_graph.value(subject=spec_component_details.spec_component_node,
                                                             predicate=MUST.queryName)
        spec_component.value = get_query_from_querybuilder(triple_store=spec_component_details.mustrd_triple_store,
                                                           folder_name=query_folder,
                                                           query_name=query_name)
    # If anzo specific function is called but no anzo defined
    else:
        raise ValueError(f"You must define {MUST.AnzoConfig} to use {MUST.AnzoQueryBuilderSparqlSource}")

    spec_component.queryType = spec_component_details.spec_graph.value(subject=spec_component_details.spec_component_node,
                                                                       predicate=MUST.queryType)
    return spec_component


@get_spec_component.method((MUST.AnzoGraphmartStepSparqlSource, MUST.when))
def _get_spec_component_AnzoGraphmartStepSparqlSource(spec_component_details: SpecComponentDetails) -> SpecComponent:
    spec_component = init_spec_component(spec_component_details.predicate)

    # Get WHEN specComponent from query builder
    if spec_component_details.mustrd_triple_store["type"] == MUST.Anzo:
        query_step_uri = spec_component_details.spec_graph.value(subject=spec_component_details.spec_component_node,
                                                             predicate=MUST.anzoQueryStep)
        spec_component.value = get_query_from_step(triple_store=spec_component_details.mustrd_triple_store,
                                                    query_step_uri=query_step_uri)
    # If anzo specific function is called but no anzo defined
    else:
        raise ValueError(f"You must define {MUST.AnzoConfig} to use {MUST.AnzoGraphmartStepSparqlSource}")

    spec_component.queryType = spec_component_details.spec_graph.value(subject=spec_component_details.spec_component_node,
                                                                       predicate=MUST.queryType)
    return spec_component

@get_spec_component.method((MUST.AnzoGraphmartQueryDrivenTemplatedStepSparqlSource, MUST.when))
def _get_spec_component_AnzoGraphmartQueryDrivenTemplatedStepSparqlSource(spec_component_details: SpecComponentDetails) -> SpecComponent:
    spec_component = init_spec_component(spec_component_details.predicate, spec_component_details.mustrd_triple_store["type"] )

    # Get WHEN specComponent from query builder
    if spec_component_details.mustrd_triple_store["type"] == MUST.Anzo:
        query_step_uri = spec_component_details.spec_graph.value(subject=spec_component_details.spec_component_node,
                                                             predicate=MUST.anzoQueryStep)
        queries = get_queries_from_templated_step(triple_store=spec_component_details.mustrd_triple_store,
                                                    query_step_uri=query_step_uri)
        spec_component.paramQuery= queries["param_query"]
        spec_component.queryTemplate = queries["query_template"]
    # If anzo specific function is called but no anzo defined
    else:
        raise ValueError(f"You must define {MUST.AnzoConfig} to use {MUST.AnzoGraphmartQueryDrivenTemplatedStepSparqlSource}")

    spec_component.queryType = spec_component_details.spec_graph.value(subject=spec_component_details.spec_component_node,
                                                                       predicate=MUST.queryType)
    return spec_component

@get_spec_component.method((MUST.AnzoGraphmartLayerSparqlSource, MUST.when))
def _get_spec_component_AnzoGraphmartLayerSparqlSource(spec_component_details: SpecComponentDetails) -> list:
    spec_components = []
    # Get the ordered  WHEN specComponents which is the transform and query driven template queries for the Layer
    if spec_component_details.mustrd_triple_store["type"] == MUST.Anzo:
        graphmart_layer_uri = spec_component_details.spec_graph.value(subject=spec_component_details.spec_component_node,
                                                             predicate=MUST.anzoGraphmartLayer)
        queries = get_queries_for_layer(triple_store=spec_component_details.mustrd_triple_store,
                                                    graphmart_layer_uri=graphmart_layer_uri)
    # If anzo specific function is called but no anzo defined
    else:
        raise ValueError(f"This test specification is specific to Anzo and can only be run against that platform.")
    for query in queries:
        spec_component = init_spec_component(spec_component_details.predicate, spec_component_details.mustrd_triple_store["type"])
        spec_component.value = query.get("query") 
        spec_component.paramQuery = query.get("param_query")
        spec_component.queryTemplate = query.get("query_template")
        if spec_component.value:
            spec_component.queryType = spec_component_details.spec_graph.value(subject=spec_component_details.spec_component_node,
                                                                       predicate=MUST.queryType)
        else:
            spec_component.queryType  = MUST.AnzoQueryDrivenUpdateSparql   
        spec_components += [spec_component]
    return spec_components

@get_spec_component.method(Default)
def _get_spec_component_default(spec_component_details: SpecComponentDetails) -> SpecComponent:
    raise ValueError(
        f"Invalid combination of data source type ({spec_component_details.data_source_type}) and "
        f"spec component ({spec_component_details.predicate})")


def init_spec_component(predicate: URIRef, triple_store_type: URIRef = None ) -> GivenSpec | WhenSpec | ThenSpec | TableThenSpec:
    if predicate == MUST.given:
        spec_component = GivenSpec()
    elif predicate == MUST.when:
        if triple_store_type == MUST.Anzo:
            spec_component = AnzoWhenSpec()
        else:
            spec_component = WhenSpec()
    elif predicate == MUST.then:
        spec_component = ThenSpec()
    else:
        spec_component = SpecComponent()
    return spec_component


def get_spec_component_nodes(subject: URIRef, predicate: URIRef, spec_graph: Graph) -> List[Node]:
    spec_component_nodes = []
    for spec_component_node in spec_graph.objects(subject=subject, predicate=predicate):
        spec_component_nodes.append(spec_component_node)
    # It shouldn't even be possible to get this far as an empty node indicates an invalid RDF file
    if spec_component_nodes is None:
        raise ValueError(f"specComponent Node empty for {subject} {predicate}")
    return spec_component_nodes


def get_spec_component_from_file(path: Path) -> str:
    # project_root = get_project_root()
    # file_path = Path(os.path.join(project_root, path))

    if path.is_dir():
        raise ValueError(f"Path {path} is a directory, expected a file")

    try:
        content = path.read_text()
    except FileNotFoundError:
        raise
    return str(content)


def get_spec_from_statements(subject: URIRef,
                             predicate: URIRef,
                             spec_graph: Graph) -> Graph:
    statements_query = f"""
    prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> 

    CONSTRUCT {{ ?s ?p ?o }}
    {{
            <{subject}> <{predicate}> [
                a <{MUST.StatementsDataset}> ;
                <{MUST.hasStatement}> [
                    a rdf:Statement ;
                    rdf:subject ?s ;
                    rdf:predicate ?p ;
                    rdf:object ?o ;
                ] ;
            ]

    }}
    """
    results = spec_graph.query(statements_query).graph
    return results.serialize(format="ttl")


def get_spec_from_table(subject: URIRef,
                        predicate: URIRef,
                        spec_graph: Graph) -> pandas.DataFrame:
    then_query = f"""
    SELECT ?then ?order ?variable ?binding
    WHERE {{ {{
         <{subject}> <{predicate}> [
                a <{MUST.TableDataset}> ;
                <{MUST.hasRow}> [ 
                    <{MUST.hasBinding}> [
                        <{MUST.variable}> ?variable ;
                        <{MUST.boundValue}> ?binding ; ] ; 
                            ] ; ].}} 
    OPTIONAL {{ <{subject}> <{predicate}> [
                a <{MUST.TableDataset}> ;
                <{MUST.hasRow}> [  sh:order ?order ;
                                    <{MUST.hasBinding}> [
                            <{MUST.variable}> ?variable ;
                            <{MUST.boundValue}> ?binding ; ] ;
                        ] ; ].}}
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
            data_dict[i.variable.value].append(str(i.binding))
            if type(i.binding) == Literal:
                literal_type = str(XSD.string)
                if hasattr(i.binding, "datatype") and i.binding.datatype:
                    literal_type = str(i.binding.datatype)
                data_dict[i.variable.value + "_datatype"].append(literal_type)
            else:
                data_dict[i.variable.value + "_datatype"].append(str(XSD.anyURI))

    # convert dict to Series to avoid problem with array length
    for key, value in data_dict.items():
        series_list.append(pandas.Series(value, name=key))

    df = pandas.concat(series_list, axis=1)
    df.fillna('', inplace=True)

    return df


def get_when_bindings(subject: URIRef,
                      spec_graph: Graph) -> dict:
    when_bindings_query = f"""SELECT ?variable ?binding {{ <{subject}> <{MUST.when}> [ a <{MUST.TextSparqlSource}> ; <{MUST.hasBinding}> [ <{MUST.variable}> ?variable ; <{MUST.boundValue}> ?binding ; ] ; ]  ;}}"""
    when_bindings = spec_graph.query(when_bindings_query)

    if len(when_bindings.bindings) == 0:
        return {}
    else:
        bindings = {}
        for binding in when_bindings:
            bindings[Variable(binding.variable.value)] = binding.binding
        return bindings


def is_then_select_ordered(subject: URIRef, predicate: URIRef, spec_graph: Graph) -> bool:
    ask_select_ordered = f"""
    ASK {{
    {{SELECT (count(?binding) as ?totalBindings) {{  
    <{subject}> <{predicate}> [
                a <{MUST.TableDataset}> ;
                <{MUST.hasRow}> [ <{MUST.hasBinding}> [
                                    <{MUST.variable}> ?variable ;
                                    <{MUST.boundValue}> ?binding ;
                            ] ; 
              ]
            ]
}} }}
    {{SELECT (count(?binding) as ?orderedBindings) {{    
    <{subject}> <{predicate}> [
                a <{MUST.TableDataset}> ;
       <{MUST.hasRow}> [ sh:order ?order ;
                    <{MUST.hasBinding}> [ 
                    <{MUST.variable}> ?variable ;
                                    <{MUST.boundValue}> ?binding ;
                            ] ; 
              ]
            ]
}} }}
    FILTER(?totalBindings = ?orderedBindings)
}}"""
    is_ordered = spec_graph.query(ask_select_ordered)
    return is_ordered.askAnswer
