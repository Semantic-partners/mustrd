import os
from dataclasses import dataclass
from itertools import groupby
from pathlib import Path

import pandas
import requests
from rdflib import RDF, Graph, URIRef, Variable, Literal, XSD, util

from mustrdAnzo import get_spec_component_from_graphmart, get_query_from_querybuilder
from namespace import MUST
from utils import get_project_root
from multimethods import MultiMethod, Default


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
class ThenSpec(SpecComponent):
    value: Graph = Graph()
    ordered: bool = False


@dataclass
class TableThenSpec(ThenSpec):
    value: pandas.DataFrame = pandas.DataFrame()


@dataclass
class SpecComponentDetails:
    subject: URIRef
    predicate: URIRef
    spec_graph: Graph
    mustrd_triple_store: dict
    spec_component_node: URIRef
    data_source_type: URIRef
    folder_location: Path


def parse_spec_component(subject: URIRef,
                         predicate: URIRef,
                         spec_graph: Graph,
                         folder_location: Path,
                         mustrd_triple_store: dict) -> SpecComponent:
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
                folder_location=folder_location)
            spec_components.append(get_spec_component(spec_component_details))
        # all_data_source_types.extend(data_source_types)
    # return all_data_source_types
    # merge multiple graphs into one, give error if spec is When or TableThen
    return combine_specs(spec_components)


def get_spec_component_type(spec_components):
    # Get the type of the first object in the list
    spec_type = type(spec_components[0])

    # Loop through the remaining objects in the list and check their types
    for spec_component in spec_components[1:]:
        if type(spec_component) != spec_type:
            # If an object has a different type, raise an error
            raise ValueError("All spec components must be of the same type")

    # If all objects have the same type, return the type
    return spec_type


def combine_specs_dispatch(spec_components):
    spec_type = get_spec_component_type(spec_components)
    return spec_type


combine_specs = MultiMethod("combine_specs", combine_specs_dispatch)


@combine_specs.method(GivenSpec)
def _combine_given_specs(spec_components):
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
def _combine_when_specs(spec_components):
    if len(spec_components) != 1:
        raise ValueError(f"Parsing of multiple components of {MUST.when} not implemented")
    spec_component = spec_components[0]
    return spec_component


@combine_specs.method(ThenSpec)
def _combine_then_specs(spec_components):
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
def _combine_given_specs(spec_components):
    if len(spec_components) != 1:
        raise ValueError(f"Parsing of multiple components of MUST.then for tables not implemented")
    return spec_components[0]


@combine_specs.method(Default)
def _combine_specs_default(spec_components):
    raise ValueError(f"Parsing of multiple components of this type not implemented")


# https://github.com/Semantic-partners/mustrd/issues/99
def get_spec_component_dispatch(spec_component_details: SpecComponentDetails):
    # spec_component_node = get_spec_component_nodes(subject, predicate, spec_graph)
    # data_source_type = get_data_source_types(subject, predicate, spec_graph, spec_component_node)
    return spec_component_details.data_source_type, spec_component_details.predicate


def get_data_source_types(subject, predicate, spec_graph, source_node):
    data_source_types = []
    for data_source_type in spec_graph.objects(subject=source_node, predicate=RDF.type):
        data_source_types.append(data_source_type)
    # data_source_type = spec_graph.value(subject=source_node, predicate=RDF.type)
    if len(data_source_types) == 0:
        raise ValueError(f"Node has no rdf type {subject} {predicate}")
    return data_source_types


get_spec_component = MultiMethod("get_spec_component", get_spec_component_dispatch)


@get_spec_component.method((MUST.FolderDataSource, MUST.given))
def _get_spec_component_folderdatasource_given(spec_component_details: SpecComponentDetails) -> GivenSpec:
    spec_component = init_spec_component(spec_component_details.predicate)

    file_name = spec_component_details.spec_graph.value(subject=spec_component_details.spec_component_node,
                                                             predicate=MUST.fileName)

    path = Path(os.path.join(spec_component_details.folder_location, file_name))
    spec_component.value = Graph().parse(data=get_spec_spec_component_from_file(path))
    return spec_component


@get_spec_component.method((MUST.FileDataSource, MUST.given))
def _get_spec_component_filedatasource_given(spec_component_details: SpecComponentDetails) -> GivenSpec:
    spec_component = init_spec_component(spec_component_details.predicate)

    file_path = Path(spec_component_details.spec_graph.value(subject=spec_component_details.spec_component_node,
                                                             predicate=MUST.file))
    project_root = get_project_root()
    path = Path(os.path.join(project_root, file_path))
    spec_component.value = Graph().parse(data=get_spec_spec_component_from_file(path))
    return spec_component


@get_spec_component.method((MUST.FileDataSource, MUST.when))
def _get_spec_component_filedatasource_when(spec_component_details: SpecComponentDetails) -> SpecComponent:
    spec_component = init_spec_component(spec_component_details.predicate)

    file_path = Path(spec_component_details.spec_graph.value(subject=spec_component_details.spec_component_node, predicate=MUST.file))
    project_root = get_project_root()
    path = Path(os.path.join(project_root, file_path))
    spec_component.value = get_spec_spec_component_from_file(path)

    get_query_type(spec_component_details.predicate, spec_component_details.spec_graph, spec_component,
                   spec_component_details.spec_component_node)
    return spec_component


@get_spec_component.method((MUST.FileDataSource, MUST.then))
def _get_spec_component_filedatasource_then(spec_component_details: SpecComponentDetails) -> SpecComponent:
    spec_component = init_spec_component(spec_component_details.predicate)

    file_path = Path(spec_component_details.spec_graph.value(subject=spec_component_details.spec_component_node, predicate=MUST.file))
    project_root = get_project_root()
    path = Path(os.path.join(project_root, file_path))
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
            file_format = util.guess_format(path)
        except AttributeError:
            raise ValueError(f"Unsupported file format: {path.suffix}")

        if file_format is not None:
            g = Graph()
            g.parse(data=get_spec_spec_component_from_file(path), format=file_format)
            spec_component.value = g
            return spec_component


@get_spec_component.method((MUST.TextDataSource, MUST.when))
def _get_spec_component_TextDataSource(spec_component_details: SpecComponentDetails) -> SpecComponent:
    spec_component = init_spec_component(spec_component_details.predicate)

    # Get specComponent directly from config file (in text string)
    spec_component.value = str(
        spec_component_details.spec_graph.value(subject=spec_component_details.spec_component_node, predicate=MUST.queryText))
    spec_component.bindings = get_when_bindings(spec_component_details.subject, spec_component_details.spec_graph)
    get_query_type(spec_component_details.predicate, spec_component_details.spec_graph, spec_component,
                   spec_component_details.spec_component_node)

    return spec_component


# https://github.com/Semantic-partners/mustrd/issues/98
@get_spec_component.method((MUST.HttpDataSource, MUST.given))
@get_spec_component.method((MUST.HttpDataSource, MUST.when))
@get_spec_component.method((MUST.HttpDataSource, MUST.then))
def _get_spec_component_HttpDataSource(spec_component_details: SpecComponentDetails) -> SpecComponent:
    spec_component = init_spec_component(spec_component_details.predicate)

    # Get specComponent with http GET protocol
    spec_component.value = requests.get(
        spec_component_details.spec_graph.value(subject=spec_component_details.spec_component_node, predicate=MUST.dataSourceUrl)).content
    get_query_type(spec_component_details.predicate, spec_component_details.spec_graph, spec_component,
                   spec_component_details.spec_component_node)
    return spec_component


@get_spec_component.method((MUST.TableDataSource, MUST.then))
def _get_spec_component_TableDataSource(spec_component_details: SpecComponentDetails) -> SpecComponent:
    table_then = TableThenSpec()
    # get specComponent from ttl table
    table_then.value = get_spec_from_table(spec_component_details.subject, spec_component_details.predicate,
                                           spec_component_details.spec_graph)
    table_then.ordered = is_then_select_ordered(spec_component_details.subject, spec_component_details.predicate,
                                                spec_component_details.spec_graph)
    return table_then


@get_spec_component.method((MUST.EmptyTableResult, MUST.then))
def _get_spec_component_EmptyTableResult(spec_component_details: SpecComponentDetails) -> SpecComponent:
    spec_component = TableThenSpec()
    return spec_component


@get_spec_component.method((MUST.EmptyGraphResult, MUST.then))
def _get_spec_component_EmptyGraphResult(spec_component_details: SpecComponentDetails) -> SpecComponent:
    spec_component = init_spec_component(spec_component_details.predicate)

    return spec_component


@get_spec_component.method((MUST.StatementsDataSource, MUST.given))
@get_spec_component.method((MUST.StatementsDataSource, MUST.then))
def _get_spec_component_StatementsDataSource(spec_component_details: SpecComponentDetails) -> SpecComponent:
    spec_component = init_spec_component(spec_component_details.predicate)

    spec_component.value = Graph().parse(
        data=get_spec_from_statements(spec_component_details.subject, spec_component_details.predicate,
                                      spec_component_details.spec_graph))
    return spec_component


# https://github.com/Semantic-partners/mustrd/issues/38
@get_spec_component.method((MUST.AnzoGraphmartDataSource, MUST.given))
@get_spec_component.method((MUST.AnzoGraphmartDataSource, MUST.then))
def _get_spec_component_AnzoGraphmartDataSource(spec_component_details: SpecComponentDetails) -> SpecComponent:
    spec_component = init_spec_component(spec_component_details.predicate)

    if spec_component_details.mustrd_triple_store["type"] == MUST.Anzo:
        # Get GIVEN or THEN from anzo graphmart
        graphmart = spec_component_details.spec_graph.value(subject=spec_component_details.spec_component_node, predicate=MUST.graphmart)
        layer = spec_component_details.spec_graph.value(subject=spec_component_details.spec_component_node, predicate=MUST.layer)
        spec_component.value = get_spec_component_from_graphmart(
            triple_store=spec_component_details.mustrd_triple_store, graphmart=graphmart,
            layer=layer)
    else:
        raise ValueError(f"You must define {MUST.AnzoConfig} to use {MUST.AnzoGraphmartDataSource}")

    return spec_component


@get_spec_component.method((MUST.AnzoQueryBuilderDataSource, MUST.when))
def _get_spec_component_AnzoQueryBuilderDataSource(spec_component_details: SpecComponentDetails) -> SpecComponent:
    spec_component = init_spec_component(spec_component_details.predicate)

    # Get WHEN specComponent from query builder
    if spec_component_details.mustrd_triple_store["type"] == MUST.Anzo:
        query_folder = spec_component_details.spec_graph.value(subject=spec_component_details.spec_component_node, predicate=MUST.queryFolder)
        query_name = spec_component_details.spec_graph.value(subject=spec_component_details.spec_component_node, predicate=MUST.queryName)
        spec_component.value = get_query_from_querybuilder(triple_store=spec_component_details.mustrd_triple_store,
                                                           folder_name=query_folder,
                                                           query_name=query_name)
    # If anzo specific function is called but no anzo defined
    else:
        raise ValueError(f"You must define {MUST.AnzoConfig} to use {MUST.AnzoQueryBuilderDataSource}")

    get_query_type(spec_component_details.predicate, spec_component_details.spec_graph, spec_component,
                   spec_component_details.spec_component_node)
    return spec_component


@get_spec_component.method(Default)
def _get_spec_component_default(spec_component_details: SpecComponentDetails) -> SpecComponent:
    # spec_component_node = get_spec_component_nodes(spec_component_details.subject, spec_component_details.predicate, spec_component_details.spec_graph)
    # data_source_type = get_data_source_types(spec_component_details.subject, spec_component_details.predicate, spec_component_details.spec_graph, spec_component_node)
    raise ValueError(
        f"Invalid combination of data source type ({spec_component_details.data_source_type}) and predicate ({spec_component_details.predicate})")


# https://github.com/Semantic-partners/mustrd/issues/87
def init_spec_component(predicate):
    if predicate == MUST.given:
        spec_component = GivenSpec()
    elif predicate == MUST.when:
        spec_component = WhenSpec()
    elif predicate == MUST.then:
        spec_component = ThenSpec()
    else:
        spec_component = SpecComponent()

    # spec_component_node = get_spec_component_nodes(subject, predicate, spec_graph)

    return spec_component


def get_query_type(predicate, spec_graph, spec_component, spec_component_node):
    if predicate == URIRef('https://mustrd.com/model/when'):
        spec_component.queryType = spec_graph.value(subject=spec_component_node, predicate=MUST.queryType)


def get_spec_component_nodes(subject, predicate, spec_graph):
    spec_component_nodes = []
    for spec_component_node in spec_graph.objects(subject=subject, predicate=predicate):
        spec_component_nodes.append(spec_component_node)
    # spec_component_node = spec_graph.value(subject=subject, predicate=predicate)
    # It shouldn't even be possible to get this far as an empty node indicates an invalid RDF file
    if spec_component_nodes is None:
        raise ValueError(f"specComponent Node empty for {subject} {predicate}")
    return spec_component_nodes


def get_spec_spec_component_from_file(path: Path) -> str:
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
                a <{MUST.StatementsDataSource}> ;
                <{MUST.statements}> [
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


# https://github.com/Semantic-partners/mustrd/issues/50
def get_spec_from_table(subject: URIRef,
                        predicate: URIRef,
                        spec_graph: Graph) -> pandas.DataFrame:
    then_query = f"""
    SELECT ?then ?order ?variable ?binding
    WHERE {{ {{
         <{subject}> <{predicate}> [
                a <{MUST.TableDataSource}> ;
                <{MUST.rows}> [ 
                    <{MUST.row}> [
                        <{MUST.variable}> ?variable ;
                        <{MUST.binding}> ?binding ; ] ; 
                            ] ; ].}} 
    OPTIONAL {{ <{subject}> <{predicate}> [
                a <{MUST.TableDataSource}> ;
                <{MUST.rows}> [  sh:order ?order ;
                                    <{MUST.row}> [
                            <{MUST.variable}> ?variable ;
                            <{MUST.binding}> ?binding ; ] ;
                        ] ; ].}}
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
    when_bindings_query = f"""SELECT ?variable ?binding {{ <{subject}> <{MUST.when}> [ a <{MUST.TextDataSource}> ; <{MUST.bindings}> [ <{MUST.variable}> ?variable ; <{MUST.binding}> ?binding ; ] ; ]  ;}}"""
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
                a <{MUST.TableDataSource}> ;
                <{MUST.rows}> [ <{MUST.row}> [
                                    <{MUST.variable}> ?variable ;
                                    <{MUST.binding}> ?binding ;
                            ] ; 
              ]
            ]
}} }}
    {{SELECT (count(?binding) as ?orderedBindings) {{    
    <{subject}> <{predicate}> [
                a <{MUST.TableDataSource}> ;
       <{MUST.rows}> [ sh:order ?order ;
                    <{MUST.row}> [ 
                    <{MUST.variable}> ?variable ;
                                    <{MUST.binding}> ?binding ;
                            ] ; 
              ]
            ]
}} }}
    FILTER(?totalBindings = ?orderedBindings)
}}"""
    is_ordered = spec_graph.query(ask_select_ordered)
    return is_ordered.askAnswer
