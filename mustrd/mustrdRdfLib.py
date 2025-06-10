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
