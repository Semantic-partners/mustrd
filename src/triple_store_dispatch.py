from multimethods import MultiMethod, Default
from rdflib import Graph

import logger_setup
from namespace import MUST
from mustrdGraphDb import execute_select as execute_graphdb_select
from mustrdGraphDb import execute_construct as execute_graphdb_construct
from mustrdGraphDb import execute_update as execute_graphdb_update
from mustrdAnzo import execute_select as execute_anzo_select
from mustrdAnzo import execute_construct as execute_anzo_construct
from mustrdRdfLib import execute_select as execute_rdflib_select
from mustrdRdfLib import execute_construct as execute_rdflib_construct
from mustrdRdfLib import execute_update as execute_rdflib_update


log = logger_setup.setup_logger(__name__)


def dispatch_construct(triple_store: dict, given: Graph, when: str, bindings: dict):
    to = triple_store["type"]
    log.info(f"dispatch_construct to triple store {to}")
    return to


execute_construct_spec = MultiMethod('execute_construct_spec', dispatch_construct)


@execute_construct_spec.method(MUST.RdfLib)
def execute_construct_rdflib(triple_store: dict, given: Graph, when: str, bindings: dict = None) -> Graph:
    return execute_rdflib_construct(triple_store, given, when, bindings)


@execute_construct_spec.method(MUST.GraphDb)
def execute_construct_graphdb(triple_store: dict, given: Graph, when: str, bindings: dict = None) -> Graph:
    return execute_graphdb_construct(triple_store, given, when, bindings)


@execute_construct_spec.method(MUST.Anzo)
def execute_construct_anzo(triple_store: dict, given: Graph, when: str, bindings: dict = None) -> Graph:
    return execute_anzo_construct(triple_store, given, when, bindings)


@execute_construct_spec.method(Default)
def execute_construct_default(triple_store: dict, given: Graph, when: str, bindings: dict = None):
    raise Exception(f"SPARQL CONSTRUCT not implemented for {triple_store['type']}")


def dispatch_select(triple_store: dict, given: Graph, when: str, bindings: dict):
    to = triple_store["type"]
    log.info(f"dispatch_select to triple store {to}")
    return to


execute_select_spec = MultiMethod('execute_select_spec', dispatch_select)


@execute_select_spec.method(MUST.RdfLib)
def execute_select_rdflib(triple_store: dict, given: Graph, when: str, bindings: dict = None) -> str:
    return execute_rdflib_select(triple_store, given, when, bindings)


@execute_select_spec.method(MUST.GraphDb)
def execute_select_graphdb(triple_store: dict, given: Graph, when: str, bindings: dict = None) -> str:
    return execute_graphdb_select(triple_store, given, when, bindings)


@execute_select_spec.method(MUST.Anzo)
def execute_select_anzo(triple_store: dict, given: Graph, when: str, bindings: dict = None) -> str:
    return execute_anzo_select(triple_store, given, when, bindings)


@execute_select_spec.method(Default)
def execute_select_default(triple_store: dict, given: Graph, when: str, bindings: dict = None):
    raise Exception(f"SPARQL SELECT not implemented for {triple_store['type']}")


def dispatch_update(triple_store: dict, given: Graph, when: str, bindings: dict):
    to = triple_store["type"]
    log.info(f"dispatch_update to triple store {to}")
    return to


execute_update_spec = MultiMethod('execute_update_spec', dispatch_update)


@execute_update_spec.method(MUST.RdfLib)
def execute_update_rdflib(triple_store: dict, given: Graph, when: str, bindings: dict = None) -> Graph:
    return execute_rdflib_update(triple_store, given, when, bindings)

@execute_update_spec.method(MUST.GraphDb)
def execute_update_graphdb(triple_store: dict, given: Graph, when: str, bindings: dict = None) -> Graph:
    return execute_graphdb_update(triple_store, given, when, bindings)

@execute_update_spec.method(Default)
def execute_update_default(triple_store: dict, given: Graph, when: str, bindings: dict = None):
    raise NotImplementedError(f"SPARQL UPDATE not implemented for {triple_store['type']}")


