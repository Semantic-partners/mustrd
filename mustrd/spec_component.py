import os
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Tuple, List, Type

import pandas
import requests
from rdflib import RDF, Dataset, Graph, URIRef, Variable, Literal, XSD, util
from rdflib.exceptions import ParserError
from rdflib.term import Node
import edn_format

from .mustrdAnzo import get_queries_for_layer, get_queries_from_templated_step
from .mustrdAnzo import get_query_from_querybuilder
from .namespace import MUST, TRIPLESTORE
from multimethods import MultiMethod, Default
from .utils import get_mustrd_root, rdflib_internals_quiet
import logging

log = logging.getLogger(__name__)


class UpdatableDataset(Dataset):
    """A Dataset that survives `INSERT DATA`, which rdflib 7.6's does not.

    rdflib's `evalInsertData` does `g += u.triples` with the *dataset* as `g`
    (sparql/update.py), and `Dataset.__iadd__` unpacks four-tuples — so every
    `INSERT DATA` raises `not enough values to unpack (expected 4, got 3)`.
    `ConjunctiveGraph` has no such problem, which is why mustrd used one; but it
    is deprecated and slated for removal, and it printed a deprecation warning
    naming a mustrd line on every spec a user ran.

    So: the modern class, with the one thing rdflib gets wrong about it repaired.
    Triples go to the default graph, which is where an unqualified `INSERT DATA`
    puts them (SPARQL 1.1 §3.1.3); quads keep rdflib's own behaviour, so
    `INSERT DATA { GRAPH <g> { … } }` still lands in `<g>`.

    TRIPWIRE: when rdflib fixes this, `UpdatableDataset` becomes a plain
    `Dataset` and this class goes. `test_insert_data_is_broken_on_a_plain_dataset`
    fails when that happens, which is the signal to delete it.
    """

    def __iadd__(self, other):
        statements = list(other)
        if statements and len(statements[0]) == 3:
            for triple in statements:
                self.default_graph.add(triple)
            return self
        return super().__iadd__(statements)

    def __repr__(self):
        """Without reaching `Dataset.identifier`, which rdflib 7.6 deprecates.

        This matters more than it looks. mustrd logs f-strings — `log.debug(f"…
        {triple_store}")` — and an f-string is built whether or not anything is
        listening, so a `given` sitting in that dict was repr'd on every spec of
        every run. rdflib's `Graph.__repr__` reads `self.identifier`, so each one
        printed a deprecation. Ten per run, from code the user cannot reach.

        Says something useful while it is here: how much data, in how many graphs.
        """
        with rdflib_internals_quiet():
            graph_count = sum(1 for _ in self.graphs())
            size = len(self)
        return f"<{type(self).__name__} {size} statements in {graph_count} graph(s)>"


@dataclass
class SpecComponent:
    pass


@dataclass
class GivenSpec(SpecComponent):
    value: Dataset = None


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
        # A source node may legitimately carry types mustrd does not own — e.g. the
        # query at a must:fileurl also being labelled a named query in the caller's
        # own vocabulary. Dispatch only the types mustrd has a handler for, so the
        # extras are ignored rather than fatal; if NONE are recognised, fall through
        # to the Default handler, which reports the valid combinations as before.
        known = [t for t in data_source_types
                 if (t, predicate) in get_spec_component.methods]
        for data_source_type in (known or data_source_types):
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


# Every file a run actually read, as {spec IRI: {reference as written: resolved path}}.
# Recorded at the one point where a relative reference becomes a real path, so a
# report can embed exactly what mustrd loaded and link the reference in the spec
# to it — with no second copy of the resolution rules to drift out of step.
referenced_files: dict = defaultdict(dict)


def get_file_absolute_path(spec_component_details: SpecComponentDetails, relative_file_path: str):
    """The first of the component's candidate roots where the file exists."""
    if not relative_file_path:
        raise ValueError("Cannot get absolute path of None")
    absolute_file_paths = list(map(lambda root_path: Path(os.path.join(root_path, relative_file_path)),
                                   spec_component_details.root_paths))
    for absolute_file_path in absolute_file_paths:
        if (os.path.exists(absolute_file_path)):
            referenced_files[str(spec_component_details.subject)][
                str(relative_file_path)] = str(absolute_file_path)
            return absolute_file_path
    raise FileNotFoundError(f"Could not find file {relative_file_path=} in any of the {absolute_file_paths=}")


def get_spec_component_type(spec_components: List[SpecComponent]) -> Type[SpecComponent]:
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
        # Quad-aware: `graph += other` reads the union and drops which graph each
        # triple came from, so combining two givens used to flatten any named
        # graph a .trig had contributed.
        combined = UpdatableDataset(default_union=True)
        for spec_component in spec_components:
            value = spec_component.value
            if value is None:
                continue
            if isinstance(value, Dataset):
                with rdflib_internals_quiet():
                    combined.addN((s, p, o, graph)
                                  for graph in value.graphs()
                                  for s, p, o in graph)
            else:
                combined.default_graph += value
        given_spec = GivenSpec()
        given_spec.value = combined
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
        # Graph `then`s combine by union; two tables have no such meaning, so a
        # spec gets one. Say which spec and what the rule is — the old wording
        # ("multiple components of MUST.then") read as though a single table had
        # several parts, and sent readers looking at the wrong thing.
        raise ValueError(
            f"A spec may declare at most one table must:then, found {len(spec_components)}")
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


# New (source type, predicate) combination -> register a method, don't add a
# conditional. See docs/adrs/0006-type-axis-dispatch-uses-multimethods.md
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
    # Same loader as MUST.FileDataset, so a folder-sourced given keeps its named
    # graphs too rather than only the file-sourced one.
    return load_dataset_from_file(path, spec_component)


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
def _get_spec_component_filedatasource_given(spec_component_details: SpecComponentDetails) -> GivenSpec:
    spec_component = GivenSpec()
    return load_spec_component(spec_component_details, spec_component)

@get_spec_component.method((MUST.FileDataset, MUST.then))
def _get_spec_component_filedatasource_then(spec_component_details: SpecComponentDetails) -> ThenSpec:
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

        if file_format is None:
            # This used to fall off the end of the function and return None,
            # which surfaced much later as an unrelated error about a spec
            # component that was never built.
            raise ValueError(f"Unsupported file format: {path.suffix}")

        # Parse into a quad-aware graph, always — a quad format (.trig, .nq,
        # .trix) parsed into a plain Graph puts its quads in the store's named
        # contexts, which that Graph cannot see, so the component came back
        # EMPTY. An empty `given` then read as no given at all, and rdflib specs
        # were rejected with "Unable to run Inherited State tests on Rdflib" — a
        # message about a feature the spec never asked for.
        # default_union so an unqualified query still reads every graph, which is
        # what a given without a GRAPH clause has always done.
        quads = UpdatableDataset(default_union=True)
        try:
            parse_into_dataset(quads, get_spec_component_from_file(path), file_format)
        except ParserError as e:
            log.error(f"Problem parsing {path}, error of type {type(e)}")
            raise ValueError(f"Problem parsing {path}, error of type {type(e)}")
        # A `then` is compared triple-by-triple against the query's result graph,
        # which has no named graphs to compare against — so it keeps the flat
        # Graph it has always been. Only `given` keeps its contexts, which is
        # what lets a GRAPH clause in the `when` resolve.
        spec_component.value = quads if isinstance(spec_component, GivenSpec) else flatten_to_graph(quads)
        return spec_component


QUAD_FORMATS = {"trig", "nquads", "trix", "json-ld", "hext"}


def parse_into_dataset(dataset: Dataset, data: str, file_format: str) -> None:
    """Parse into `dataset`, quietly, whatever the format carries.

    Triples go straight into the default graph. `Dataset.parse` would reach it
    via `default_context`, which rdflib 7.6 deprecates — and the warning it emits
    names OUR line, so every mustrd user sees a deprecation they cannot act on.

    Quads have to go through `Dataset.parse`, because only the quad parsers know
    which graph each statement belongs to. rdflib's own TriG parser builds a
    ConjunctiveGraph internally and warns about it (rdflib 7.6, trig.py), which
    is likewise not ours to fix and nothing a mustrd user can do anything about,
    so it is silenced here rather than printed fourteen times a run.
    """
    if file_format not in QUAD_FORMATS:
        dataset.default_graph.parse(data=data, format=file_format)
        return

    with rdflib_internals_quiet():
        dataset.parse(data=data, format=file_format)


def flatten_to_graph(quads: Dataset) -> Graph:
    """The union of every graph in the dataset, as one plain Graph."""
    g = Graph()
    with rdflib_internals_quiet():
        for triple in quads.triples((None, None, None)):
            g.add(triple)
        for prefix, namespace in quads.namespaces():
            g.bind(prefix, namespace)
    return g


@get_spec_component.method((MUST.FileSparqlSource, MUST.when))
def _get_spec_component_filedatasource_when(spec_component_details: SpecComponentDetails) -> SpecComponent:
    spec_component = WhenSpec()
    file_path = get_file_or_fileurl(spec_component_details)
    # file_path = Path(str(spec_component_details.spec_graph.value(subject=spec_component_details.spec_component_node,
    #                                                              predicate=MUST.file)))
    spec_component.value = get_spec_component_from_file(get_file_absolute_path(spec_component_details, file_path))
    spec_component.bindings = get_when_bindings(spec_component_details.subject, spec_component_details.spec_graph)
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

    data = get_spec_from_statements(spec_component_details.subject, spec_component_details.predicate,
                                    spec_component_details.spec_graph)

    quads = UpdatableDataset(default_union=True)
    # Into the DEFAULT graph, not a named one. An unqualified `DELETE ... WHERE`
    # operates on the dataset's default graph (SPARQL 1.1 §3.1.3), so given data
    # sitting in a named graph is matched by the WHERE — a default_union dataset
    # reads as the union — and then not deleted. rdflib <= 7.1.4 deleted it anyway;
    # 7.6.0 is conformant, which is what broke every update spec. Reads are
    # unaffected either way, so the default graph is simply the correct home.
    quads.default_graph.parse(data=data)

    # As with a file-sourced component: a `given` keeps its contexts so a GRAPH
    # clause can resolve, a `then` is levelled, because it is compared against a
    # result graph that has no named graphs in it.
    spec_component.value = quads if isinstance(spec_component, GivenSpec) \
        else flatten_to_graph(quads)
    return spec_component


def require_anzo(spec_component_details: SpecComponentDetails, source_type: URIRef):
    """Guard: these sources only resolve against an Anzo triple store.

    The get_spec_component multimethod dispatches on the spec's declared source,
    but whether the *configured* triple store is Anzo is a runtime fact, not a
    dispatch key — so each Anzo source checks it up front through here rather than
    repeating the same if/else.
    """
    if spec_component_details.mustrd_triple_store["type"] != TRIPLESTORE.Anzo:
        raise ValueError(f"You must define {TRIPLESTORE.Anzo} to use {source_type}")


@get_spec_component.method((MUST.AnzoGraphmartDataset, MUST.given))
@get_spec_component.method((MUST.AnzoGraphmartDataset, MUST.then))
def _get_spec_component_AnzoGraphmartDataset(spec_component_details: SpecComponentDetails) -> SpecComponent:
    require_anzo(spec_component_details, MUST.AnzoGraphmartDataset)
    # Choose GivenSpec or ThenSpec based on the predicate in spec_component_details
    if spec_component_details.predicate == MUST.given:
        spec_component = GivenSpec()
    else:
        spec_component = ThenSpec()
    # Get GIVEN or THEN from anzo graphmart
    spec_component.spec_component_details = spec_component_details
    return spec_component


@get_spec_component.method((MUST.AnzoQueryBuilderSparqlSource, MUST.when))
def _get_spec_component_AnzoQueryBuilderSparqlSource(spec_component_details: SpecComponentDetails) -> SpecComponent:
    require_anzo(spec_component_details, MUST.AnzoQueryBuilderSparqlSource)
    spec_component = WhenSpec()

    # Get WHEN specComponent from query builder
    query_folder = spec_component_details.spec_graph.value(subject=spec_component_details.spec_component_node,
                                                           predicate=MUST.queryFolder)
    query_name = spec_component_details.spec_graph.value(subject=spec_component_details.spec_component_node,
                                                         predicate=MUST.queryName)
    spec_component.value = get_query_from_querybuilder(triple_store=spec_component_details.mustrd_triple_store,
                                                       folder_name=query_folder,
                                                       query_name=query_name)
    spec_component.queryType = spec_component_details.spec_graph.value(
        subject=spec_component_details.spec_component_node,
        predicate=MUST.queryType)
    return spec_component


@get_spec_component.method((MUST.AnzoGraphmartStepSparqlSource, MUST.when))
def _get_spec_component_AnzoGraphmartStepSparqlSource(spec_component_details: SpecComponentDetails) -> SpecComponent:
    require_anzo(spec_component_details, MUST.AnzoGraphmartStepSparqlSource)
    spec_component = AnzoWhenSpec()

    # Get WHEN specComponent from query builder
    query_step_uri = spec_component_details.spec_graph.value(subject=spec_component_details.spec_component_node,
                                                             predicate=MUST.anzoQueryStep)
    spec_component.spec_component_details = spec_component_details
    spec_component.query_step_uri = query_step_uri
    spec_component.queryType = spec_component_details.spec_graph.value(
        subject=spec_component_details.spec_component_node,
        predicate=MUST.queryType)
    return spec_component


@get_spec_component.method((MUST.AnzoGraphmartQueryDrivenTemplatedStepSparqlSource, MUST.when))
def _get_spec_component_AnzoGraphmartQueryDrivenTemplatedStepSparqlSource(spec_component_details: SpecComponentDetails) -> SpecComponent: # noqa
    require_anzo(spec_component_details, MUST.AnzoGraphmartQueryDrivenTemplatedStepSparqlSource)
    spec_component = WhenSpec(
        spec_component_details.predicate, spec_component_details.mustrd_triple_store["type"])

    # Get WHEN specComponent from query builder
    query_step_uri = spec_component_details.spec_graph.value(subject=spec_component_details.spec_component_node,
                                                             predicate=MUST.anzoQueryStep)
    queries = get_queries_from_templated_step(triple_store=spec_component_details.mustrd_triple_store,
                                              query_step_uri=query_step_uri)
    spec_component.paramQuery = queries["param_query"]
    spec_component.queryTemplate = queries["query_template"]
    spec_component.queryType = spec_component_details.spec_graph.value(
        subject=spec_component_details.spec_component_node,
        predicate=MUST.queryType)
    return spec_component


@get_spec_component.method((MUST.AnzoGraphmartLayerSparqlSource, MUST.when))
def _get_spec_component_AnzoGraphmartLayerSparqlSource(spec_component_details: SpecComponentDetails) -> list:
    require_anzo(spec_component_details, MUST.AnzoGraphmartLayerSparqlSource)
    spec_components = []
    # Get the ordered  WHEN specComponents which is the transform and query driven template queries for the Layer
    graphmart_layer_uri = spec_component_details.spec_graph.value(
        subject=spec_component_details.spec_component_node,
        predicate=MUST.anzoGraphmartLayer)
    queries = get_queries_for_layer(triple_store=spec_component_details.mustrd_triple_store,
                                    graphmart_layer_uri=graphmart_layer_uri)
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


# NOTE: the (SpadeEdnGroupSource, when) handler lives further down as
# _get_spec_component_spade_edn_group_source_when. An earlier duplicate was
# registered on this same key here and never dispatched (the later registration
# won); it has been removed.


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
        content = path.read_text(encoding='utf-8')
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
    # this query was restricted to queries of type MUST.TextSparqlSource, which seems unnecessary when get_when_bindings is called from specific methods
    when_bindings_query = f"""SELECT ?variable ?binding {{ <{subject}> <{MUST.when}> [ a ?queryType ;
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

        if step_type == Keyword("sparql-file"):
            try:
                step_file = step.get(Keyword("filepath"))
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
            except FileNotFoundError:
                raise ValueError(f"SPARQL file not found: {resolved_step_file}")
        elif step_type == Keyword("sparql-template-file"):
            when_spec = AnzoWhenSpec(
                queryTemplate=get_spec_component_from_file(Path(absolute_file_path).parent / step.get(Keyword("template-filepath"))),
                paramQuery=get_spec_component_from_file(Path(absolute_file_path).parent / step.get(Keyword("parameters-filepath"))),
                spec_component_details=spec_component_details
            )
            when_spec.queryType = MUST.AnzoQueryDrivenUpdateSparql
        else:
            raise ValueError(f"Unsupported step type in EDN file: {step_type}")

        when_specs.append(when_spec)

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
