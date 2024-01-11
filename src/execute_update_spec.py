from multimethods import MultiMethod
import logging 
from rdflib import Graph, URIRef
from namespace import MUST
from mustrdGraphDb import execute_update as execute_graphdb_update


def dispatch_update(triple_store: dict, when: str, bindings: dict) -> URIRef:
    to = triple_store["type"]
    logging.info(f"dispatch_update to triple store {to}")
    return to


execute_update_spec = MultiMethod('execute_update_spec', dispatch_update)


@execute_update_spec.method(MUST.GraphDb)
def execute_update_graphdb(triple_store: dict, given: Graph, when: str, bindings: dict = None) -> Graph:
    return execute_graphdb_update(triple_store, given, when, bindings)
