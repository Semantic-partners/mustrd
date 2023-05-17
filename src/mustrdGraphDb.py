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

# https://github.com/Semantic-partners/mustrd/issues/22
def upload_given(triple_store: dict, given: Graph):
    try:
        graph = "default"
        if triple_store['input_graph']: 
            graph = urllib.parse.urlencode({'graph': triple_store['input_graph']})
        url = f"{triple_store['url']}:{triple_store['port']}/repositories/{triple_store['repository']}/rdf-graphs/service?{graph}"
        manage_graphdb_response(requests.put(url=url,
                                                        auth=(triple_store['username'], triple_store['password']),data = given.serialize(format="ttl"),
                                                        headers = {'Content-Type': 'text/turtle'}))
    except ConnectionError:
        raise


# https://github.com/Semantic-partners/mustrd/issues/122
def execute_select(triple_store: dict, given: Graph, when: str, bindings: dict = None) -> str:
    if triple_store["input_graph"] is None:
        drop_default_graph(triple_store)
    else:
        clear_graph(triple_store)
    upload_given(triple_store, given)
    return post_query(triple_store, when, "application/sparql-results+json", bindings)

def execute_construct(triple_store: dict, given: Graph, when: str, bindings: dict = None) -> Graph:
    if triple_store["input_graph"] is None:
        drop_default_graph(triple_store)
    else:
        clear_graph(triple_store)
    upload_given(triple_store, given)
    return Graph().parse(post_query(triple_store, when, "text/turtle", bindings))

def execute_update(triple_store: dict, given: Graph, when: str, bindings: dict = None) -> Graph:
    if triple_store["input_graph"] is None:
        drop_default_graph(triple_store)
    else:
        clear_graph(triple_store)
    upload_given(triple_store, given)
    post_update_query(triple_store, when, bindings)

    return  Graph().parse(data=post_query(triple_store, "CONSTRUCT {?s ?p ?o} where { ?s ?p ?o }", 'text/turtle'))


def clear_graph(triple_store: dict):
    post_update_query(triple_store, f"CLEAR GRAPH <{triple_store['input_graph']}>")


def drop_default_graph(triple_store: dict):
    post_update_query(triple_store, "DROP DEFAULT")


def post_update_query(triple_store: dict, query: str, params: dict = None):
    add_graph_to_params(params, triple_store["input_graph"])
    try:
        return manage_graphdb_response(requests.post(url=f"{triple_store['url']}:{triple_store['port']}/repositories/{triple_store['repository']}/statements",
                                                    data = query, params=params, auth=(triple_store['username'], triple_store['password']), headers={'Content-Type': 'application/sparql-update'}))
    except ConnectionError:
        raise

def post_query(triple_store: dict, query: str, accept: str, params: dict = None):
    headers = {
        'Content-Type': 'application/sparql-query', 
        'Accept': accept
    }
    add_graph_to_params(params, triple_store["input_graph"])
    try:
        return manage_graphdb_response(requests.post(url=f"{triple_store['url']}:{triple_store['port']}/repositories/{triple_store['repository']}",
                                                    data = query, params=params, auth=(triple_store['username'], triple_store['password']), headers=headers))
    except ConnectionError:
        raise

def add_graph_to_params(params, graph):
    if params:
        params['default-graph-uri'] = graph
    else:
        params = {'default-graph-uri': graph}

