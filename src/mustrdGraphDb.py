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
        # graph store PUT drop silently the graph or default and upload the payload
        # https://www.w3.org/TR/sparql11-http-rdf-update/#http-put
        manage_graphdb_response(requests.put(url=url,
                                                        auth=(triple_store['username'], triple_store['password']),data = given.serialize(format="ttl"),
                                                        headers = {'Content-Type': 'text/turtle'}))
    except ConnectionError:
        raise

def parse_bindings(bindings: dict = None):
    return None if not bindings else {f"${k}" : str(v.n3()) for k, v in bindings.items()}

# https://github.com/Semantic-partners/mustrd/issues/122
def execute_select(triple_store: dict, given: Graph, when: str, bindings: dict = None) -> str:
    upload_given(triple_store, given)
    return post_query(triple_store, when, "application/sparql-results+json", parse_bindings(bindings))

def execute_construct(triple_store: dict, given: Graph, when: str, bindings: dict = None) -> Graph:
    upload_given(triple_store, given)
    return Graph().parse(data=post_query(triple_store, when, "text/turtle", parse_bindings(bindings)))

def execute_update(triple_store: dict, given: Graph, when: str, bindings: dict = None) -> Graph:
    upload_given(triple_store, given)
    post_update_query(triple_store, when, parse_bindings(bindings))
    return  Graph().parse(data=post_query(triple_store, "CONSTRUCT {?s ?p ?o} where { ?s ?p ?o }", 'text/turtle'))

def post_update_query(triple_store: dict, query: str, params: dict = None):
    params = add_graph_to_params(params, triple_store["input_graph"])
    query = insert_graph_into_query(query, triple_store["input_graph"] )
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
    params = add_graph_to_params(params, triple_store["input_graph"])
    try:
        return manage_graphdb_response(requests.post(url=f"{triple_store['url']}:{triple_store['port']}/repositories/{triple_store['repository']}",
                                                    data = query, params=params, auth=(triple_store['username'], triple_store['password']), headers=headers))
    except ConnectionError:
        raise

def add_graph_to_params(params, graph):
    graph = graph or "http://rdf4j.org/schema/rdf4j#nil" 
    if params:
        params['default-graph-uri'] = graph
    else:
        params = {'default-graph-uri': graph}
    return params

def insert_graph_into_query(query, input_graph):
    if _contains_clause('insert', query):
        query= insert_graph_into_clause('insert', query, input_graph)
    if _contains_clause('insert data', query):
        query= insert_graph_into_clause('insert data', query, input_graph)
    if _contains_clause('where', query):
        query = insert_graph_into_clause('where', query, input_graph)
    return query

def insert_graph_into_clause(clause_type, query, input_graph) -> str:
    if clause_type == 'where':
        regex=f"(?i)({clause_type}\s*{{)(.+}})"
    else:
        regex=f"(?i)({clause_type}\s*{{)(.+?}})"
    start, end = re.search(regex, query).groups()
    new_clause= start + 'GRAPH <' + input_graph + '> {' + end + '} '
    return re.sub( regex, new_clause, query)

def _contains_clause(clause_type, query):
   return re.search(f"(?i){clause_type}\s*{{.+?}}",query)
