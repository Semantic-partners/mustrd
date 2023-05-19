from rdflib import Graph
from requests import RequestException


def execute_select(triple_store: dict, given: Graph, when: str, bindings: dict = None) -> str:
    try:
        return given.query(when, initBindings=bindings).serialize(format="json").decode("utf-8")
    except Exception as e:
        raise RequestException(e)


def execute_construct(triple_store: dict, given: Graph, when: str, bindings: dict = None) -> Graph:
    try:
        return given.query(when, initBindings=bindings).graph
    except Exception as e:
        raise RequestException(e)


def execute_update(triple_store: dict, given: Graph, when: str, bindings: dict = None) -> Graph:
    try:
        result = given
        result.update(when, initBindings=bindings)
        return result
    except Exception as e:
        raise RequestException(e)
