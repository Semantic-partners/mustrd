from pyparsing import ParseException
from rdflib import Graph
from requests import RequestException
import logging


def execute_select(triple_store: dict, given: Graph, when: str, bindings: dict = None) -> str:
    try:
        return given.query(when, initBindings=bindings).serialize(format="json").decode("utf-8")
    except ParseException:
        raise
    except Exception as e:
        raise RequestException(e)


def execute_construct(triple_store: dict, given: Graph, when: str, bindings: dict = None) -> Graph:
    try:
        logger = logging.getLogger(__name__)
        logger.debug(f"Executing CONSTRUCT query: {when} with bindings: {bindings}")


        result_graph = given.query(when, initBindings=bindings).graph
        logger.debug(f"CONSTRUCT query executed successfully, resulting graph has {len(result_graph)} triples.")
        return result_graph
    except ParseException:
        raise
    except Exception as e:
        raise RequestException(e)


def execute_update(triple_store: dict, given: Graph, when: str, bindings: dict = None) -> Graph:
    try:
        result = given
        result.update(when, initBindings=bindings)
        return result
    except ParseException:
        raise
    except Exception as e:
        raise RequestException(e)
