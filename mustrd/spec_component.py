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
from pathlib import Path
from typing import Tuple, List, Type

import pandas
import requests
from rdflib import RDF, Graph, URIRef, Variable, Literal, XSD, util, ConjunctiveGraph
from rdflib.exceptions import ParserError
from rdflib.term import Node
from rdflib.plugins.stores.memory import Memory
import edn_format

from . import logger_setup
from .mustrdAnzo import get_queries_for_layer, get_queries_from_templated_step
from .mustrdAnzo import get_query_from_querybuilder
from .namespace import MUST, TRIPLESTORE
from multimethods import MultiMethod, Default
from .utils import get_mustrd_root
from urllib.parse import urlparse

log = logger_setup.setup_logger(__name__)


@dataclass
class SpecComponent:
    pass


@dataclass
class GivenSpec(SpecComponent):
    value: ConjunctiveGraph = None


@dataclass
class WhenSpec(SpecComponent):
    value: str = None
    queryType: URIRef = None
    bindings: dict = None


@dataclass
class AnzoWhenSpec(WhenSpec):
    paramQuery: str = None
    queryTemplate: str = None
    spec_component_details: any = None


@dataclass
class SpadeEdnGroupSourceWhenSpec(WhenSpec):
    file: str = None
    groupId: str = None


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
    root_paths: list


def get_path(path_type: str, file_name, spec_component_details: SpecComponentDetails) -> Path:
    if path_type in spec_component_details.run_config:
        relative_path = os.path.join(spec_component_details.run_config[path_type], file_name)
    else:
        relative_path = file_name
    return get_file_absolute_path(spec_component_details, relative_path)


def parse_spec_component(subject: URIRef,
                         predicate: URIRef,
                         spec_graph: Graph,
                         run_config: dict,
                         mustrd_triple_store: dict) -> GivenSpec | WhenSpec | ThenSpec | TableThenSpec:
    spec_component_nodes = get_spec_component_nodes(subject, predicate, spec_graph)
    spec_components = []
    for spec_component_node in spec_component_nodes:
        data_source_types = get_data_source_types(subject, predicate, spec_graph, spec_component_node)
        for data_source_type in data_source_types:
            log.debug(f"parse_spec_component {spec_component_node} {data_source_type} {mustrd_triple_store=}")
            spec_component_details = SpecComponentDetails(
                subject=subject,
                predicate=predicate,
                spec_graph=spec_graph,
                mustrd_triple_store=mustrd_triple_store,
                spec_component_node=spec_component_node,
                data_source_type=data_source_type,
                run_config=run_config,
                root_paths=get_components_roots(spec_graph, subject, run_config))

            # get_spec_component potentially talks to anzo for EVERY spec, massively slowing things down
            # can we defer it to run time?
            spec_component = get_spec_component(spec_component_details)
            if isinstance(spec_component, list):
                spec_components += spec_component
            else:
                spec_components += [spec_component]
    # merge multiple graphs into one, give error if spec config is a TableThen
    # print(f"calling multimethod with {spec_components}")
    return combine_specs(spec_components)


# Here we retrieve all the possible root paths for a specification component.
# This defines the order of priority between root paths which is:
# 1) Path where the spec is located
# 2) spec_path defined in mustrd test configuration files or cmd line argument
# 3) data_path defined in mustrd test configuration files or cmd line argument
# 4) Mustrd source folder: In case of default resources packaged with mustrd source
# (will be in venv when mustrd is called as library)
# We intentionally don't try for absolute files, but you should feel free to argue that we should do
def get_components_roots(spec_graph: Graph, subject: URIRef, run_config: dict):
    where_did_i_load_this_spec_from = spec_graph.value(subject=subject,
                                                       predicate=MUST.specSourceFile)
    roots = []
    if not where_did_i_load_this_spec_from:
        log.error(f"""{where_did_i_load_this_spec_from=} was None for test_spec={subject},
                  we didn't set the test specifications specSourceFile when loading, spec_graph={spec_graph}""")
    else:
        roots.append(Path(os.path.dirname(where_did_i_load_this_spec_from)))
    if run_config and 'spec_path' in run_config:
        roots.append(Path(run_config['spec_path']))
    if run_config and 'data_path' in run_config:
        roots.append(run_config['data_path'])
    roots.append(get_mustrd_root())

    return roots


# From the list of component potential roots, return the first path that exists
def get_file_absolute_path(spec_component_details: SpecComponentDetails, relative_file_path: str):
    if not relative_file_path:
        raise ValueError("Cannot get absolute path of None")
    absolute_file_paths = list(map(lambda root_path: Path(os.path.join(root_path, relative_file_path)),
                                   spec_component_details.root_paths))
    for absolute_file_path in absolute_file_paths:
        if (os.path.exists(absolute_file_path)):
            return absolute_file_path
    raise FileNotFoundError(f"Could not find file {relative_file_path=} in any of the {absolute_file_paths=}")


def get_spec_component_type(spec_components: List[SpecComponent]) -> Type[SpecComponent]:
    if not spec_components:
        raise ValueError("spec_components list is empty")
    # Get the type of the first object in the list
    spec_type = type(spec_components[0])
    # Loop through the remaining objects in the list and check their types
    for spec_component in spec_components[1:]:
        if not isinstance(spec_component, spec_type):
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
        raise ValueError("Parsing of multiple components of MUST.then for tables not implemented")
    return spec_components[0]


@combine_specs.method(Default)
def _combine_specs_default(spec_components: List[SpecComponent]):
    raise ValueError(f"Parsing of multiple components of this type not implemented {spec_components}")


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
    spec_component = GivenSpec()
    return spec_component


@get_spec_component.method((MUST.FolderDataset, MUST.given))
def _get_spec_component_folderdatasource_given(spec_component_details: SpecComponentDetails) -> GivenSpec:
    spec_component = GivenSpec()

    file_name = spec_component_details.spec_graph.value(subject=spec_component_details.spec_component_node,
                                                        predicate=MUST.fileName)

    path = get_path('given_path', file_name, spec_component_details)
    try:
        spec_component.value = Graph().parse(data=get_spec_component_from_file(path))
    except ParserError as e:
        log.error(f"Problem parsing {path}, error of type {type(e)}")
        raise ValueError(f"Problem parsing {path}, error of type {type(e)}")
    return spec_component


@get_spec_component.method((MUST.FolderSparqlSource, MUST.when))
def _get_spec_component_foldersparqlsource_when(spec_component_details: SpecComponentDetails) -> GivenSpec:
    spec_component = WhenSpec()

    file_name = spec_component_details.spec_graph.value(subject=spec_component_details.spec_component_node,
                                                        predicate=MUST.fileName)

    path = get_path('when_path', file_name, spec_component_details)
    spec_component.value = get_spec_component_from_file(path)
    spec_component.queryType = spec_component_details.spec_graph.value(
        subject=spec_component_details.spec_component_node,
        predicate=MUST.queryType)
    return spec_component


@get_spec_component.method((MUST.FolderDataset, MUST.then))
def _get_spec_component_folderdatasource_then(spec_component_details: SpecComponentDetails) -> ThenSpec:
    spec_component = ThenSpec()

    file_name = spec_component_details.spec_graph.value(subject=spec_component_details.spec_component_node,
                                                        predicate=MUST.fileName)
    path = get_path('then_path', file_name, spec_component_details)

    return load_dataset_from_file(path, spec_component)


@get_spec_component.method((MUST.FileDataset, MUST.given))
def _get_spec_component_filedatasource(spec_component_details: SpecComponentDetails) -> GivenSpec:
    spec_component = GivenSpec()
    return load_spec_component(spec_component_details, spec_component)

@get_spec_component.method((MUST.FileDataset, MUST.then))
def _get_spec_component_filedatasource(spec_component_details: SpecComponentDetails) -> ThenSpec:
    spec_component = ThenSpec()
    return load_spec_component(spec_component_details, spec_component)


def load_spec_component(spec_component_details, spec_component):
    file_path = get_file_or_fileurl(spec_component_details)
    file_path = Path(str(file_path))
    return load_dataset_from_file(get_file_absolute_path(spec_component_details, file_path), spec_component)

def get_file_or_fileurl(spec_component_details):
    file_path = spec_component_details.spec_graph.value(
        subject=spec_component_details.spec_component_node,
        predicate=MUST.file
    )
    if file_path is None:
        file_path = spec_component_details.spec_graph.value(
            subject=spec_component_details.spec_component_node,
            predicate=MUST.fileurl
        )
        if file_path is not None and str(file_path).startswith("file://"):
            # Remove the 'file://' scheme to get the local path
            # we do it this quick and dirty way because the urlparse library assumes absolute paths, and strips our leading ./
            # need to confirm this approach is windows safe. 

            new_path = str(file_path)[7:]
            log.debug(f"converted {file_path=} to {new_path=}")
            file_path = new_path
    if file_path is None:
        # shacl validation will catch this, but we want to raise a more specific error
        raise ValueError("Neither MUST.file nor MUST.fileurl found for the spec component node")
    return file_path


def load_dataset_from_file(path: Path, spec_component: ThenSpec) -> ThenSpec:
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


@get_spec_component.method((MUST.FileSparqlSource, MUST.when))
def _get_spec_component_filedatasource_when(spec_component_details: SpecComponentDetails) -> SpecComponent:
    spec_component = WhenSpec()
    file_path = get_file_or_fileurl(spec_component_details)
    # file_path = Path(str(spec_component_details.spec_graph.value(subject=spec_component_details.spec_component_node,
    #                                                              predicate=MUST.file)))
    spec_component.value = get_spec_component_from_file(get_file_absolute_path(spec_component_details, file_path))

    spec_component.queryType = spec_component_details.spec_graph.value(
        subject=spec_component_details.spec_component_node,
        predicate=MUST.queryType)

    return spec_component


@get_spec_component.method((MUST.TextSparqlSource, MUST.when))
def _get_spec_component_TextSparqlSource(spec_component_details: SpecComponentDetails) -> SpecComponent:
    spec_component = WhenSpec()

    # Get specComponent directly from config file (in text string)
    spec_component.value = str(
        spec_component_details.spec_graph.value(subject=spec_component_details.spec_component_node,
                                                predicate=MUST.queryText))

    spec_component.bindings = get_when_bindings(spec_component_details.subject, spec_component_details.spec_graph)
    spec_component.queryType = spec_component_details.spec_graph.value(
        subject=spec_component_details.spec_component_node,
        predicate=MUST.queryType)
    return spec_component


def _get_spec_component_HttpDataset_shared(spec_component_details: SpecComponentDetails, spec_component):
    # Get specComponent with http GET protocol
    url = spec_component_details.spec_graph.value(
        subject=spec_component_details.spec_component_node,
        predicate=MUST.dataSourceUrl
    )
    if not url:
        raise ValueError("MUST.dataSourceUrl is missing for HttpDataset")
    response = requests.get(str(url))
    response.raise_for_status()
    spec_component.value = response.content
    if hasattr(spec_component, "queryType"):
        spec_component.queryType = spec_component_details.spec_graph.value(
            subject=spec_component_details.spec_component_node,
            predicate=MUST.queryType)
    return spec_component

@get_spec_component.method((MUST.HttpDataset, MUST.given))
def _get_spec_component_HttpDataset_given(spec_component_details: SpecComponentDetails) -> GivenSpec:
    return _get_spec_component_HttpDataset_shared(spec_component_details, GivenSpec())

@get_spec_component.method((MUST.HttpDataset, MUST.when))
def _get_spec_component_HttpDataset_when(spec_component_details: SpecComponentDetails) -> WhenSpec:
    return _get_spec_component_HttpDataset_shared(spec_component_details, WhenSpec())

@get_spec_component.method((MUST.HttpDataset, MUST.then))
def _get_spec_component_HttpDataset_then(spec_component_details: SpecComponentDetails) -> ThenSpec:
    return _get_spec_component_HttpDataset_shared(spec_component_details, ThenSpec())


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
    spec_component = ThenSpec()

    return spec_component


@get_spec_component.method((MUST.StatementsDataset, MUST.given))
@get_spec_component.method((MUST.StatementsDataset, MUST.then))
def _get_spec_component_StatementsDataset(spec_component_details: SpecComponentDetails) -> SpecComponent:
    # Choose GivenSpec or ThenSpec based on the predicate in spec_component_details
    if spec_component_details.predicate == MUST.given:
        spec_component = GivenSpec()
    else:
        spec_component = ThenSpec()
    store = Memory()
    g = URIRef("http://localhost:7200/test-graph")
    spec_component.value = ConjunctiveGraph(store=store)
    spec_graph = Graph(store=store, identifier=g)

    data = get_spec_from_statements(spec_component_details.subject, spec_component_details.predicate,
                                    spec_component_details.spec_graph)
    spec_graph.parse(data=data)
    return spec_component


@get_spec_component.method((MUST.AnzoGraphmartDataset, MUST.given))
@get_spec_component.method((MUST.AnzoGraphmartDataset, MUST.then))
def _get_spec_component_AnzoGraphmartDataset(spec_component_details: SpecComponentDetails) -> SpecComponent:
    # Choose GivenSpec or ThenSpec based on the predicate in spec_component_details
    if spec_component_details.predicate == MUST.given:
        spec_component = GivenSpec()
    else:
        spec_component = ThenSpec()

    if spec_component_details.mustrd_triple_store["type"] == TRIPLESTORE.Anzo:
        # Get GIVEN or THEN from anzo graphmart
        spec_component.spec_component_details = spec_component_details
    else:
        raise ValueError(f"You must define {TRIPLESTORE.Anzo} to use {MUST.AnzoGraphmartDataset}")

    return spec_component


@get_spec_component.method((MUST.AnzoQueryBuilderSparqlSource, MUST.when))
def _get_spec_component_AnzoQueryBuilderSparqlSource(spec_component_details: SpecComponentDetails) -> SpecComponent:
    spec_component = WhenSpec()

    # Get WHEN specComponent from query builder
    if spec_component_details.mustrd_triple_store["type"] == TRIPLESTORE.Anzo:
        query_folder = spec_component_details.spec_graph.value(subject=spec_component_details.spec_component_node,
                                                               predicate=MUST.queryFolder)
        query_name = spec_component_details.spec_graph.value(subject=spec_component_details.spec_component_node,
                                                             predicate=MUST.queryName)
        spec_component.value = get_query_from_querybuilder(triple_store=spec_component_details.mustrd_triple_store,
                                                           folder_name=query_folder,
                                                           query_name=query_name)
    # If anzo specific function is called but no anzo defined
    else:
        raise ValueError(f"You must define {TRIPLESTORE.Anzo} to use {MUST.AnzoQueryBuilderSparqlSource}")

    spec_component.queryType = spec_component_details.spec_graph.value(
        subject=spec_component_details.spec_component_node,
        predicate=MUST.queryType)
    return spec_component


@get_spec_component.method((MUST.AnzoGraphmartStepSparqlSource, MUST.when))
def _get_spec_component_AnzoGraphmartStepSparqlSource(spec_component_details: SpecComponentDetails) -> SpecComponent:
    spec_component = AnzoWhenSpec()

    # Get WHEN specComponent from query builder
    if spec_component_details.mustrd_triple_store["type"] == TRIPLESTORE.Anzo:
        query_step_uri = spec_component_details.spec_graph.value(subject=spec_component_details.spec_component_node,
                                                                 predicate=MUST.anzoQueryStep)
        spec_component.spec_component_details = spec_component_details
        spec_component.query_step_uri = query_step_uri
        # spec_component.value = get_query_from_step(triple_store=spec_component_details.mustrd_triple_store,
        #                                            query_step_uri=query_step_uri)
    # If anzo specific function is called but no anzo defined
    else:
        raise ValueError(f"You must define {TRIPLESTORE.Anzo} to use {MUST.AnzoGraphmartStepSparqlSource}")

    spec_component.queryType = spec_component_details.spec_graph.value(
        subject=spec_component_details.spec_component_node,
        predicate=MUST.queryType)
    return spec_component


@get_spec_component.method((MUST.AnzoGraphmartQueryDrivenTemplatedStepSparqlSource, MUST.when))
def _get_spec_component_AnzoGraphmartQueryDrivenTemplatedStepSparqlSource(spec_component_details: SpecComponentDetails) -> SpecComponent: # noqa
    spec_component = WhenSpec(
        spec_component_details.predicate, spec_component_details.mustrd_triple_store["type"])

    # Get WHEN specComponent from query builder
    if spec_component_details.mustrd_triple_store["type"] == TRIPLESTORE.Anzo:
        query_step_uri = spec_component_details.spec_graph.value(subject=spec_component_details.spec_component_node,
                                                                 predicate=MUST.anzoQueryStep)
        queries = get_queries_from_templated_step(triple_store=spec_component_details.mustrd_triple_store,
                                                  query_step_uri=query_step_uri)
        spec_component.paramQuery = queries["param_query"]
        spec_component.queryTemplate = queries["query_template"]
    # If anzo specific function is called but no anzo defined
    else:
        raise ValueError(f"""You must define {TRIPLESTORE.Anzo}
                         to use {MUST.AnzoGraphmartQueryDrivenTemplatedStepSparqlSource}""")

    spec_component.queryType = spec_component_details.spec_graph.value(
        subject=spec_component_details.spec_component_node,
        predicate=MUST.queryType)
    return spec_component


@get_spec_component.method((MUST.AnzoGraphmartLayerSparqlSource, MUST.when))
def _get_spec_component_AnzoGraphmartLayerSparqlSource(spec_component_details: SpecComponentDetails) -> list:
    spec_components = []
    # Get the ordered  WHEN specComponents which is the transform and query driven template queries for the Layer
    if spec_component_details.mustrd_triple_store["type"] == TRIPLESTORE.Anzo:
        graphmart_layer_uri = spec_component_details.spec_graph.value(
            subject=spec_component_details.spec_component_node,
            predicate=MUST.anzoGraphmartLayer)
        queries = get_queries_for_layer(triple_store=spec_component_details.mustrd_triple_store,
                                        graphmart_layer_uri=graphmart_layer_uri)
    # If anzo specific function is called but no anzo defined
    else:
        raise ValueError("This test specification is specific to Anzo and can only be run against that platform.")
    for query in queries:
        spec_component = WhenSpec(
            spec_component_details.predicate, spec_component_details.mustrd_triple_store["type"])
        spec_component.value = query.get("query")
        spec_component.paramQuery = query.get("param_query")
        spec_component.queryTemplate = query.get("query_template")
        spec_component.spec_component_details = spec_component_details
        if spec_component.value:
            spec_component.queryType = spec_component_details.spec_graph.value(
                subject=spec_component_details.spec_component_node,
                predicate=MUST.queryType)
        else:
            spec_component.queryType = MUST.AnzoQueryDrivenUpdateSparql
        spec_components += [spec_component]
    return spec_components


@get_spec_component.method(Default)
def _get_spec_component_default(spec_component_details: SpecComponentDetails) -> SpecComponent:
    valid_combinations = [key for key in get_spec_component.methods.keys() if key != Default]

    if (spec_component_details.data_source_type, spec_component_details.predicate) not in valid_combinations:
        valid_types = ', '.join([f"({data_source_type}, {predicate})" for data_source_type, predicate in valid_combinations])
        raise ValueError(
            f"Invalid combination of data source type ({spec_component_details.data_source_type}) and "
            f"spec component ({spec_component_details.predicate}). Valid combinations are: {valid_types}"
        )
    raise ValueError(
        f"Invalid combination of data source type ({spec_component_details.data_source_type}) and "
        f"spec component ({spec_component_details.predicate})")


@get_spec_component.method((MUST.SpadeEdnGroupSource, MUST.when))
def _get_spec_component_spadeednsource_when(spec_component_details: SpecComponentDetails) -> SpadeEdnGroupSourceWhenSpec:
    from edn_format import Keyword

    spec_component = SpadeEdnGroupSourceWhenSpec()
    spec_component.file = spec_component_details.spec_graph.value(
        subject=spec_component_details.spec_component_node,
        predicate=MUST.fileName
    )
    spec_component.groupId = spec_component_details.spec_graph.value(
        subject=spec_component_details.spec_component_node,
        predicate=MUST.groupId
    )
    spec_component.queryType = spec_component_details.spec_graph.value(
        subject=spec_component_details.spec_component_node,
        predicate=MUST.queryType
    )

    # Initialize `value` by parsing the `file` attribute if available
    if spec_component.file:
        try:
            with open(spec_component.file, "r") as edn_file:
                edn_content = edn_file.read()
                parsed_edn = edn_format.loads(edn_content)

                # Extract group data based on group ID
                step_groups = parsed_edn.get(Keyword("step-groups"), [])
                group_data = next((item for item in step_groups if item.get(Keyword("group-id")) == spec_component.groupId), None)

                if not group_data:
                    raise ValueError(f"Group ID {spec_component.groupId} not found in EDN file {spec_component.file}")

                # Create a list of WhenSpec objects
                when_specs = []
                for step in group_data.get(Keyword("steps"), []):
                    step_type = step.get(Keyword("type"))
                    step_file = step.get(Keyword("filepath"))

                    if step_type == Keyword("sparql-file"):
                        when_specs.append(WhenSpec(value=step_file, queryType=MUST.InsertSparql))

                spec_component.value = when_specs
        except Exception as e:
            log.error(f"Failed to parse EDN file {spec_component.file}: {e}")
            spec_component.value = None

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
    # query the spec to get the expected result to convert to dataframe for comparison
    then_query = f"""
        prefix sh:        <http://www.w3.org/ns/shacl#>
            SELECT ?row ?variable ?binding ?order
            WHERE {{
                 <{subject}> <{predicate}> [
                        a <{MUST.TableDataset}> ;
                        <{MUST.hasRow}> ?row ].
                          ?row  <{MUST.hasBinding}> [
                                <{MUST.variable}> ?variable ;
                                <{MUST.boundValue}> ?binding ; ] .
                          OPTIONAL {{ ?row sh:order ?order . }}
                                     .}}
             ORDER BY ?order"""

    expected_results = spec_graph.query(then_query)
    # get the unique row ids form the result to form the index of the results dataframe
    index = {str(row.row) for row in expected_results}
    # get the unique variables to form the columns of the results dataframe
    columns = set()
    for row in expected_results:
        columns.add(row.variable.value)
        columns.add(row.variable.value + "_datatype")
    # add an additional column for the sort order (if any) of the results
    columns.add("order")
    # create an empty dataframe to populate with the results data
    df = pandas.DataFrame(index=list(index), columns=list(columns))
    # fill the dataframe with the results data
    for row in expected_results:
        df.loc[str(row.row), row.variable.value] = str(row.binding)
        df.loc[str(row.row), "order"] = row.order
        if isinstance(row.binding, Literal):
            literal_type = str(XSD.string)
            if hasattr(row.binding, "datatype") and row.binding.datatype:
                literal_type = str(row.binding.datatype)
            df.loc[str(row.row), row.variable.value + "_datatype"] = literal_type
        else:
            df.loc[str(row.row), row.variable.value + "_datatype"] = str(XSD.anyURI)
    # use the sort order sort the results
    df.sort_values(by="order", inplace=True)
    # drop the order column and replace the rowid index with a numeric one and replace empty values with spaces
    df.drop(columns="order", inplace=True)
    df.reset_index(drop=True, inplace=True)
    df.fillna('', inplace=True)
    return df


def get_when_bindings(subject: URIRef,
                      spec_graph: Graph) -> dict:
    when_bindings_query = f"""SELECT ?variable ?binding {{ <{subject}> <{MUST.when}> [ a <{MUST.TextSparqlSource}> ;
    <{MUST.hasBinding}> [ <{MUST.variable}> ?variable ;
    <{MUST.boundValue}> ?binding ; ] ; ]  ;}}"""
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


@get_spec_component.method((MUST.SpadeEdnGroupSource, MUST.when))
def _get_spec_component_spade_edn_group_source_when(spec_component_details: SpecComponentDetails) -> SpecComponent:
    spec_component = SpadeEdnGroupSourceWhenSpec()

    # Retrieve the file path for the EDN file
    file_path = get_file_or_fileurl(spec_component_details)
    absolute_file_path = get_file_absolute_path(spec_component_details, file_path)

    # Parse the EDN file
    try:
        edn_content = Path(absolute_file_path).read_text()
        edn_data = edn_format.loads(edn_content)
    except FileNotFoundError:
        raise ValueError(f"EDN file not found: {absolute_file_path}")
    except edn_format.EDNDecodeError as e:
        raise ValueError(f"Failed to parse EDN file {absolute_file_path}: {e}")

    # Retrieve and normalize the group ID
    group_id = spec_component_details.spec_graph.value(
        subject=spec_component_details.spec_component_node,
        predicate=MUST.groupId
    )

    if not group_id:
        raise ValueError("groupId is missing for SpadeEdnGroupSource")

    if str(group_id).startswith(':'):
        group_id = str(group_id).lstrip(':')
        from edn_format import Keyword
        group_id = Keyword(group_id)
    else:
        group_id = str(group_id)

    # Extract the relevant group data
    step_groups = edn_data.get(Keyword("step-groups"), [])
    group_data = next((item for item in step_groups if item.get(Keyword("group-id")) == group_id), None)

    if not group_data:
        raise ValueError(f"Group ID {group_id} not found in EDN file {absolute_file_path}")

    # Create a list of WhenSpec objects
    when_specs = []
    for step in group_data.get(Keyword("steps"), []):
        step_type = step.get(Keyword("type"))
        step_file = step.get(Keyword("filepath"))

        if step_type == Keyword("sparql-file"):
            try:
                # Resolve the file path relative to the EDN file's location
                resolved_step_file = Path(absolute_file_path).parent / step_file
                with open(resolved_step_file, 'r') as sparql_file:
                    sparql_query = sparql_file.read()

                # Assume the individuals are ConstructSparql queries
                # won't be true for ASK, but good for now.
                when_spec = WhenSpec(
                    value=sparql_query,
                    queryType=MUST.UpdateSparql, 
                    bindings=None
                )
                when_specs.append(when_spec)
            except FileNotFoundError:
                raise ValueError(f"SPARQL file not found: {resolved_step_file}")

    spec_component.file = str(absolute_file_path)
    spec_component.groupId = group_id
    spec_component.value = when_specs
    spec_component.queryType = MUST.SpadeEdnGroupSource  # Correct query type

    return spec_component


def parse_sparql_query(query_string: str):
    """
    Parses a SPARQL query string and returns a query object.
    """
    try:
        from rdflib.plugins.sparql.parser import parseQuery
        return parseQuery(query_string)
    except Exception as e:
        raise ValueError(f"Failed to parse SPARQL query: {e}")
