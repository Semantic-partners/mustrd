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

import urllib.parse
import re

import requests
from pyparsing import ParseException
from rdflib import Graph
from requests import ConnectionError, HTTPError


# https://github.com/Semantic-partners/mustrd/issues/72
def manage_graphdb_response(response) -> str:
    content_string = response.content.decode("utf-8")
    if response.status_code == 200:
        return content_string
    elif response.status_code == 204:
        pass
    elif response.status_code == 401:
        raise HTTPError(f"GraphDB authentication error, status code: {response.status_code}, content: {content_string}")
    elif response.status_code == 406:
        raise HTTPError(f"GraphDB  error, status code: {response.status_code}, content: {content_string}")
    else:
        raise Exception(f"GraphDb error, status code: {response.status_code}, content: {content_string}")


# wrap the entire select in another select to add the graph, allows for a more complicated where
def insert_graph(when, input_graph):
    new_when = f"SELECT * WHERE {{ GRAPH <{input_graph}> {{ {when} }} }}"
    return new_when


def parse_bindings(bindings: dict):
    bindings_string = ""
    for key, value in bindings.items():
        encoded_value = urllib.parse.quote_plus(f'{value.n3()}')
        bindings_string += f'&${key}={encoded_value}'
    return bindings_string


def execute_select(triple_store: dict, given: Graph, when: str, bindings: dict = None) -> str:

    if triple_store["input_graph"] is None:
        drop_default_graph(triple_store)
    else:
        clear_graph(triple_store)
        when = insert_graph(when, triple_store["input_graph"])
    upload_given(triple_store, given)
    bindings_string = ""
    if bindings:
        bindings_string = parse_bindings(bindings)
    return post_select_query(triple_store, f"{when}{bindings_string}")

def _contains_clause(clause_type, query) -> bool:
    if re.search(f"(?i){clause_type}[ ]*{{.+?}}",query):
        return True
    else:
        return False

def execute_construct(triple_store: dict, given: Graph, when: str, bindings: dict = None) -> Graph:
    if "where {" not in when.lower():
        raise ParseException(pstr='GraphDB Implementation: No WHERE clause in query.')

    if triple_store["input_graph"] is None:
        drop_default_graph(triple_store)
    else:
        clear_graph(triple_store)
        split_when = when.lower().split("where {", 1)
        when = split_when[0] + "where { GRAPH <" + triple_store["input_graph"] + "> {" + split_when[1] + "}"
    upload_given(triple_store, given)
    bindings_string = ""
    if bindings:
        bindings_string = parse_bindings(bindings)
    return Graph().parse(data=post_construct_query(triple_store, f"{when}{bindings_string}"))

def insert_graph_into_clause(clause_type, query, input_graph) -> str:
    if clause_type == 'where':
        start, end = re.search(f"(?i)({clause_type}[ ]*{{)(.+}})", query).groups()
    else:
        start, end = re.search(f"(?i)({clause_type}[ ]*{{)(.+?}})", query).groups()
    return start + 'GRAPH <' + input_graph + '> {' + end + '} '

def insert_graph_into_query(when, input_graph):
    delete_clause = insert_clause = where_clause = ''
    if _contains_clause('delete', when):
        delete_clause = insert_graph_into_clause('delete', when, input_graph)
    if _contains_clause('delete data', when):
        delete_clause = insert_graph_into_clause('delete data', when, input_graph)
    if _contains_clause('insert', when):
        insert_clause = insert_graph_into_clause('insert', when, input_graph)
    if _contains_clause('insert data', when):
        insert_clause = insert_graph_into_clause('insert data', when, input_graph)
    if _contains_clause('where', when):
        where_clause = insert_graph_into_clause('where', when, input_graph)
    return delete_clause + insert_clause + where_clause


def execute_update(triple_store: dict, given: Graph, when: str, bindings: dict = None) -> Graph:

    if triple_store["input_graph"] is None:
        drop_default_graph(triple_store)
    else:
        clear_graph(triple_store)
        when = insert_graph_into_query(when, triple_store["input_graph"] )
    upload_given(triple_store, given)
    bindings_string = ""
    if bindings:
        bindings_string = parse_bindings(bindings)
    post_update_query(triple_store, f"{when}{bindings_string}")

    #now fetch the resulting rdf
    if triple_store["input_graph"] is None:
        query = "CONSTRUCT {?s ?p ?o} where { ?s ?p ?o }"
    else:
        query=f"CONSTRUCT {{?s ?p ?o}} where {{GRAPH <{triple_store['input_graph']}> {{ ?s ?p ?o }}}}"

    return  Graph().parse(data=post_construct_query(triple_store, query))



# https://github.com/Semantic-partners/mustrd/issues/22
def upload_given(triple_store: dict, given: Graph):
    serialized_given = given.serialize(format="nt")
    if triple_store["input_graph"] is None:
        post_update_query(triple_store, urllib.parse.quote_plus(f"INSERT DATA {{ {serialized_given} }}"))
    else:
        post_update_query(triple_store, urllib.parse.quote_plus(f"INSERT DATA {{graph <{triple_store['input_graph']}>"
                                                   f"{{{serialized_given}}}}}"))

def clear_graph(triple_store: dict):
    post_update_query(triple_store, f"CLEAR GRAPH <{triple_store['input_graph']}>")


def drop_default_graph(triple_store: dict):
    post_update_query(triple_store, "DROP DEFAULT")


def post_update_query(triple_store: dict, query: str):
    try:
        manage_graphdb_response(requests.post(
        url=f"{triple_store['url']}:{triple_store['port']}/repositories/{triple_store['repository']}/statements?update={query}",
        auth=(triple_store["username"], triple_store["password"])))
    except ConnectionError:
        raise

def post_select_query(triple_store: dict, query: str):
    try:
        return manage_graphdb_response(requests.get(
            url=f"{triple_store['url']}:{triple_store['port']}/repositories/{triple_store['repository']}?query={query}",
            auth=(triple_store["username"], triple_store["password"]),
            headers={'Accept': 'application/sparql-results+json'}))
    except ConnectionError:
        raise

def post_construct_query(triple_store: dict, query: str):
    try:
        return manage_graphdb_response(requests.get(
            url=f"{triple_store['url']}:{triple_store['port']}/repositories/{triple_store['repository']}?query={query}",
            auth=(triple_store["username"], triple_store["password"])))
    except ConnectionError:
        raise