import os
from dataclasses import dataclass
from itertools import groupby
from pathlib import Path

import pandas
import requests
from rdflib import RDF, Graph, URIRef, Variable, Literal, XSD

from mustrdAnzo import MustrdAnzo
from mustrdRdfLib import MustrdRdfLib
from namespace import MUST
from utils import get_project_root
from multimethods import MultiMethod, Default


# https://github.com/Semantic-partners/mustrd/issues/51
@dataclass
class SpecComponent:
    value: str = None
    ordered: bool = False
    bindings: dict = None

def get_spec_component_dispatch(subject: URIRef,
                       predicate: URIRef,
                       spec_graph: Graph,
                       mustrd_triple_store=MustrdRdfLib()):
    spec_component_node = get_spec_component_node(subject, predicate, spec_graph)
    source_node = get_source_node(subject, predicate, spec_graph, spec_component_node)
    data_source_type = spec_graph.value(subject=source_node, predicate=RDF.type)
    if data_source_type is None:
        raise Exception(f"Node has no rdf type {subject} {predicate}")
    return data_source_type
    
get_spec_component = MultiMethod("get_spec_component", get_spec_component_dispatch)

@get_spec_component.method(MUST.FileDataSource)
def _get_spec_component_filedatasource(subject: URIRef,
                       predicate: URIRef,
                       spec_graph: Graph,
                       mustrd_triple_store=MustrdRdfLib()) -> SpecComponent:
    spec_component, spec_component_node, source_node = init_spec_component(subject, predicate, spec_graph)

    file_path = Path(spec_graph.value(subject=source_node, predicate=MUST.file))
    project_root = get_project_root()
    path = Path(os.path.join(project_root, file_path))
    spec_component.value = get_spec_spec_component_from_file(path)
    
    validate_spec_component(predicate, spec_graph, spec_component, spec_component_node)
    return spec_component

@get_spec_component.method(MUST.textDataSource)
def _get_spec_component_textDataSource(subject: URIRef,
                       predicate: URIRef,
                       spec_graph: Graph,
                       mustrd_triple_store=MustrdRdfLib()) -> SpecComponent:
    spec_component, spec_component_node, source_node = init_spec_component(subject, predicate, spec_graph)

        # Get specComponent directly from config file (in text string)
    spec_component.value = str(spec_graph.value(subject=source_node, predicate=MUST.text))
    if predicate == MUST.when:
        spec_component.bindings = get_when_bindings(subject, spec_graph)

    validate_spec_component(predicate, spec_graph, spec_component, spec_component_node)
    return spec_component


@get_spec_component.method(MUST.HttpDataSource)
def _get_spec_component_HttpDataSource(subject: URIRef,
                       predicate: URIRef,
                       spec_graph: Graph,
                       mustrd_triple_store=MustrdRdfLib()) -> SpecComponent:
    spec_component, spec_component_node, source_node = init_spec_component(subject, predicate, spec_graph)
    # Get specComponent with http GET protocol
    spec_component.value = requests.get(spec_graph.value(subject=source_node, predicate=MUST.dataSourceUrl)).content
    validate_spec_component(predicate, spec_graph, spec_component, spec_component_node)
    return spec_component


@get_spec_component.method(MUST.TableDataSource)
def _get_spec_component_TableDataSource(subject: URIRef,
                       predicate: URIRef,
                       spec_graph: Graph,
                       mustrd_triple_store=MustrdRdfLib()) -> SpecComponent:
    spec_component, spec_component_node, source_node = init_spec_component(subject, predicate, spec_graph)
    # get specComponent from ttl table
    spec_component.value = get_spec_from_table(subject, predicate, spec_graph)
    if predicate == MUST.then:
        spec_component.ordered = is_then_select_ordered(subject, predicate, spec_graph)
    validate_spec_component(predicate, spec_graph, spec_component, spec_component_node)
    return spec_component

@get_spec_component.method(MUST.EmptyTableResult)
def _get_spec_component_EmptyTableResult(subject: URIRef,
                       predicate: URIRef,
                       spec_graph: Graph,
                       mustrd_triple_store=MustrdRdfLib()) -> SpecComponent:
    spec_component, spec_component_node, source_node = init_spec_component(subject, predicate, spec_graph)
    spec_component.value = pandas.DataFrame()
    validate_spec_component(predicate, spec_graph, spec_component, spec_component_node)
    return spec_component

@get_spec_component.method(MUST.EmptyGraphResult)
def _get_spec_component_EmptyGraphResult(subject: URIRef,
                       predicate: URIRef,
                       spec_graph: Graph,
                       mustrd_triple_store=MustrdRdfLib()) -> SpecComponent:
    spec_component, spec_component_node, source_node = init_spec_component(subject, predicate, spec_graph)
    spec_component.value = Graph()
    validate_spec_component(predicate, spec_graph, spec_component, spec_component_node)
    return spec_component


@get_spec_component.method(MUST.StatementsDataSource)
def _get_spec_component_EStatementsDataSource(subject: URIRef,
                       predicate: URIRef,
                       spec_graph: Graph,
                       mustrd_triple_store=MustrdRdfLib()) -> SpecComponent:
    spec_component, spec_component_node, source_node = init_spec_component(subject, predicate, spec_graph)
    spec_component.value = get_spec_from_statements(subject, predicate, spec_graph)
    validate_spec_component(predicate, spec_graph, spec_component, spec_component_node)
    return spec_component

@get_spec_component.method(MUST.anzoGraphmartDataSource)
def _get_spec_component_anzoGraphmartDataSource(subject: URIRef,
                       predicate: URIRef,
                       spec_graph: Graph,
                       mustrd_triple_store=MustrdRdfLib()) -> SpecComponent:
    spec_component, spec_component_node, source_node = init_spec_component(subject, predicate, spec_graph)
    if type(mustrd_triple_store) == MustrdAnzo:
        # Get GIVEN or THEN from anzo graphmart
        graphmart = spec_graph.value(subject=source_node, predicate=MUST.graphmart)
        layer = spec_graph.value(subject=source_node, predicate=MUST.layer)
        spec_component.value = mustrd_triple_store.get_spec_component_from_graphmart(graphMart=graphmart,
                                                                                            layer=layer)
    else:
        raise Exception(f"You must define {MUST.anzoConfig} to use {data_source_type}")

    validate_spec_component(predicate, spec_graph, spec_component, spec_component_node)
    return spec_component


@get_spec_component.method(MUST.anzoQueryBuilderDataSource)
def _get_spec_component_anzoQueryBuilderDataSource(subject: URIRef,
                       predicate: URIRef,
                       spec_graph: Graph,
                       mustrd_triple_store=MustrdRdfLib()) -> SpecComponent:
    spec_component, spec_component_node, source_node = init_spec_component(subject, predicate, spec_graph)
    # Get WHEN specComponent from query builder
    if type(mustrd_triple_store) == MustrdAnzo:
        query_folder = spec_graph.value(subject=source_node, predicate=MUST.queryFolder)
        query_name = spec_graph.value(subject=source_node, predicate=MUST.queryName)
        spec_component.value = mustrd_triple_store.get_query_from_querybuilder(folder_name=query_folder,
                                                                                query_name=query_name)
    # If anzo specific function is called but no anzo defined
    else:
        raise Exception(f"You must define {MUST.anzoConfig} to use {data_source_type}")

    validate_spec_component(predicate, spec_graph, spec_component, spec_component_node)
    return spec_component


def init_spec_component(subject, predicate, spec_graph):
    spec_component = SpecComponent()

    spec_component_node = get_spec_component_node(subject, predicate, spec_graph)

    source_node = get_source_node(subject, predicate, spec_graph, spec_component_node)
    return spec_component,spec_component_node,source_node

def validate_spec_component(predicate, spec_graph, spec_component, spec_component_node):
    if predicate == URIRef('https://mustrd.com/model/when'):
        spec_component.queryType = spec_graph.value(subject=spec_component_node, predicate=MUST.queryType)

def get_source_node(subject, predicate, spec_graph, spec_component_node):
    source_node = spec_graph.value(subject=spec_component_node, predicate=MUST.dataSource)
    if source_node is None:
        raise Exception(f"No data source for specComponent {subject} {predicate}")
    return source_node

def get_spec_component_node(subject, predicate, spec_graph):
    spec_component_node = spec_graph.value(subject=subject, predicate=predicate)
    if spec_component_node is None:
        raise Exception(f"specComponent Node empty for {subject} {predicate}")
    return spec_component_node


def get_spec_spec_component_from_file(path: Path) -> str:
    # project_root = get_project_root()
    # file_path = Path(os.path.join(project_root, path))

    content = ""
    if os.path.isdir(path):
        for entry in path.iterdir():
            content += entry.read_text()
    else:
        content = path.read_text()
    return str(content)


def get_spec_from_statements(subject: URIRef,
                             predicate: URIRef,
                             spec_graph: Graph) -> str:
    statements_query = f"""
    prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> 

    CONSTRUCT {{ ?s ?p ?o }}
    {{
            <{subject}> <{predicate}> [
              <{MUST.dataSource}>  [
                a <{MUST.StatementsDataSource}> ;
                <{MUST.statements}> [
                    a rdf:Statement ;
                    rdf:subject ?s ;
                    rdf:predicate ?p ;
                    rdf:object ?o ;
                ] ;
              ]
            ]

    }}
    """
    results = spec_graph.query(statements_query).graph
    return results.serialize(format="ttl")


# https://github.com/Semantic-partners/mustrd/issues/50
def get_spec_from_table(subject: URIRef,
                        predicate: URIRef,
                        spec_graph: Graph) -> pandas.DataFrame:
    then_query = f"""
    SELECT ?then ?order ?variable ?binding
    WHERE {{ {{
         <{subject}> <{predicate}> [
            <{MUST.dataSource}>  [ 
                a <{MUST.TableDataSource}> ;
                <{MUST.rows}> [ 
                    <{MUST.row}> [
                        <{MUST.variable}> ?variable ;
                        <{MUST.binding}> ?binding ; ] ; 
                            ] ; ] ; ].}} 
    OPTIONAL {{ <{subject}> <{predicate}> [
            <{MUST.dataSource}>  [ 
                a <{MUST.TableDataSource}> ;
                <{MUST.rows}> [  sh:order ?order ;
                                    <{MUST.row}> [
                            <{MUST.variable}> ?variable ;
                            <{MUST.binding}> ?binding ; ] ;
                        ] ; ] ; ].}}
    }} ORDER BY ASC(?order)"""

    expected_results = spec_graph.query(then_query)
    # return spec_graph.query(then_query).serialize(format="json").decode("utf-8")

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
    when_bindings_query = f"""SELECT ?variable ?binding {{ <{subject}> <{MUST.when}> [ <{MUST.dataSource}> [ a <{MUST.textDataSource}> ; <{MUST.bindings}> [ <{MUST.variable}> ?variable ; <{MUST.binding}> ?binding ; ] ; ] ; ]  ;}}"""
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
              <{MUST.dataSource}>  [
                a <{MUST.TableDataSource}> ;
                <{MUST.rows}> [ <{MUST.row}> [
                                    <{MUST.variable}> ?variable ;
                                    <{MUST.binding}> ?binding ;
                            ] ; 
                        ] 
              ]
            ]
}} }}
    {{SELECT (count(?binding) as ?orderedBindings) {{    
    <{subject}> <{predicate}> [
              <{MUST.dataSource}>  [
                a <{MUST.TableDataSource}> ;
       <{MUST.rows}> [ sh:order ?order ;
                    <{MUST.row}> [ 
                    <{MUST.variable}> ?variable ;
                                    <{MUST.binding}> ?binding ;
                            ] ; 
                        ] 
              ]
            ]
}} }}
    FILTER(?totalBindings = ?orderedBindings)
}}"""
    is_ordered = spec_graph.query(ask_select_ordered)
    return is_ordered.askAnswer