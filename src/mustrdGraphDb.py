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
from requests import ConnectionError, HTTPError, RequestException


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
        raise RequestException(f"GraphDb error, status code: {response.status_code}, content: {content_string}")


# wrap the entire select in another select to add the graph, allows for a more complicated where
def insert_graph(when, input_graph):
    new_when = f"SELECT * WHERE {{ GRAPH <{input_graph}> {{ {when} }} }}"
    return new_when


# https://github.com/Semantic-partners/mustrd/issues/22
def upload_given(triple_store: dict, given: Graph):
    try:
        graph = "default"
        if triple_store['input_graph']:
            graph = urllib.parse.urlencode({'graph': triple_store['input_graph']})
        url = f"{triple_store['url']}:{triple_store['port']}/repositories/{triple_store['repository']}/rdf-graphs/service?{graph}"
        manage_graphdb_response(requests.put(url=url,
                                             auth=(triple_store['username'], triple_store['password']),
                                             data=given.serialize(format="ttl"),
                                             headers={'Content-Type': 'text/turtle'}))
    except ConnectionError:
        raise


def parse_bindings(bindings: dict):
    bindings_string = ""
    for key, value in bindings.items():
        encoded_value = urllib.parse.quote_plus(f'{value.n3()}')
        bindings_string += f'&${key}={encoded_value}'
    return bindings_string


# https://github.com/Semantic-partners/mustrd/issues/122
def execute_select(triple_store: dict, given: Graph, when: str, bindings: dict = None) -> str:
    if triple_store["input_graph"] is None:
        drop_default_graph(triple_store)
    else:
        clear_graph(triple_store)
        when = insert_graph(when, triple_store["input_graph"])
    upload_given(triple_store, given)
    return post_query(triple_store, when, "application/sparql-results+json", bindings)


def _contains_clause(clause_type, query) -> bool:
    if re.search(f"(?i){clause_type}[ ]*{{.+?}}", query):
        return True
    else:
        return False


def execute_construct(triple_store: dict, given: Graph, when: str, bindings: dict = None) -> Graph:
    if triple_store["input_graph"] is None:
        drop_default_graph(triple_store)
    else:
        clear_graph(triple_store)
        split_when = when.lower().split("where {", 1)
        when = split_when[0] + "where { GRAPH <" + triple_store["input_graph"] + "> {" + split_when[1] + "}"
    upload_given(triple_store, given)
    return Graph().parse(post_query(triple_store, when, "text/turtle", bindings))


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
        when = insert_graph_into_query(when, triple_store["input_graph"])
    upload_given(triple_store, given)
    bindings_string = ""
    if bindings:
        bindings_string = parse_bindings(bindings)
    post_update_query(triple_store, f"{when}{bindings_string}")

    # now fetch the resulting rdf
    if triple_store["input_graph"] is None:
        query = "CONSTRUCT {?s ?p ?o} where { ?s ?p ?o }"
    else:
        query = f"CONSTRUCT {{?s ?p ?o}} where {{GRAPH <{triple_store['input_graph']}> {{ ?s ?p ?o }}}}"

    return Graph().parse(data=post_query(triple_store, query, 'text/turtle'))


def clear_graph(triple_store: dict):
    post_update_query(triple_store, f"CLEAR GRAPH <{triple_store['input_graph']}>")


def drop_default_graph(triple_store: dict):
    post_update_query(triple_store, "DROP DEFAULT")


def post_update_query(triple_store: dict, query: str, bindings: dict = None):
    try:
        return manage_graphdb_response(requests.post(
            url=f"{triple_store['url']}:{triple_store['port']}/repositories/{triple_store['repository']}/statements",
            data=query, params=bindings, auth=(triple_store['username'], triple_store['password']),
            headers={'Content-Type': 'application/sparql-update'}))
    except (ConnectionError, OSError):
        raise


def post_query(triple_store: dict, query: str, accept: str, bindings: dict = None):
    headers = {
        'Content-Type': 'application/sparql-query',
        'Accept': accept
    }
    try:
        return manage_graphdb_response(
            requests.post(url=f"{triple_store['url']}:{triple_store['port']}/repositories/{triple_store['repository']}",
                          data=query, params=bindings, auth=(triple_store['username'], triple_store['password']),
                          headers=headers))
    except (ConnectionError, OSError):
        raise
