from pyparsing import ParseException
from rdflib import Graph
from requests import RequestException
import logging

from .utils import rdflib_internals_quiet

logger = logging.getLogger(__name__)

# Every call here runs SPARQL against the `given`, which is quad-aware so a GRAPH
# clause can resolve. rdflib's own evaluator reaches APIs it has deprecated while
# doing that — `triples()` on a union dataset compares against `default_context`
# — and the warning names the mustrd line that called in. See
# utils.rdflib_internals_quiet.


def execute_select(triple_store: dict, given: Graph, when: str, bindings: dict = None) -> str:
    try:
        with rdflib_internals_quiet():
            return given.query(when, initBindings=bindings).serialize(format="json").decode("utf-8")
    except ParseException:
        raise
    except Exception as e:
        raise RequestException(e)


def execute_construct(triple_store: dict, given: Graph, when: str, bindings: dict = None) -> Graph:
    try:
        logger.debug(f"Executing CONSTRUCT query: {when} with bindings: {bindings}")

        with rdflib_internals_quiet():
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
        with rdflib_internals_quiet():
            result.update(when, initBindings=bindings)
        return result
    except ParseException:
        raise
    except Exception as e:
        raise RequestException(e)
