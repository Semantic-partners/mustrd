import urllib.parse
import requests
from rdflib import Graph, Literal
from requests import ConnectionError, Response

from .utils import manage_http_response


# https://github.com/Semantic-partners/mustrd/issues/72
def manage_graphdb_response(response: Response) -> str:
    # 406 stays an HTTPError (not a generic RequestException) — see manage_http_response.
    return manage_http_response(
        response, "GraphDB",
        success_codes=(200, 204), auth_codes=(401,), http_error_codes=(406,))


def upload_given(triple_store: dict, given: Graph):
    if given:
        try:
            graph = "default"
            if triple_store['input_graph']:
                graph = urllib.parse.urlencode({'graph': triple_store['input_graph']})
            url = f"{triple_store['url']}/repositories/{triple_store['repository']}" \
                  f"/rdf-graphs/service?{graph}"
            # graph store PUT drop silently the graph or default and upload the payload
            # https://www.w3.org/TR/sparql11-http-rdf-update/#http-put
            manage_graphdb_response(requests.put(url=url,
                                                 auth=(triple_store['username'], triple_store['password']),
                                                 data=given.serialize(format="ttl"),
                                                 headers={'Content-Type': 'text/turtle'}))
        except ConnectionError:
            raise


def parse_bindings(bindings: dict = None) -> dict:
    return None if not bindings else {f"${k}": str(v.n3()) for k, v in bindings.items()}


def execute_select(triple_store: dict, when: str, bindings: dict = None) -> str:
    return post_query(triple_store, when, "application/sparql-results+json", parse_bindings(bindings))


def execute_construct(triple_store: dict, when: str, bindings: dict = None) -> Graph:
    return Graph().parse(data=post_query(triple_store, when, "text/turtle", parse_bindings(bindings)))


def execute_update(triple_store: dict, when: str, bindings: dict = None) -> Graph:
    post_update_query(triple_store, when, parse_bindings(bindings))
    return Graph().parse(data=post_query(triple_store, "CONSTRUCT {?s ?p ?o} where { ?s ?p ?o }", 'text/turtle'))


def post_update_query(triple_store: dict, query: str, params: dict = None) -> str:
    params = add_graph_to_params(params, triple_store["input_graph"])
    try:
        return manage_graphdb_response(requests.post(
            url=f"{triple_store['url']}/repositories/{triple_store['repository']}/statements",
            data=query,
            params=params,
            auth=(triple_store['username'], triple_store['password']),
            headers={'Content-Type': 'application/sparql-update'}))
    except (ConnectionError, OSError):
        raise


def post_query(triple_store: dict, query: str, accept: str, params: dict = None) -> str:
    headers = {
        'Content-Type': 'application/sparql-query',
        'Accept': accept
    }
    params = add_graph_to_params(params, triple_store["input_graph"])
    try:
        return manage_graphdb_response(
            requests.post(url=f"{triple_store['url']}/repositories/{triple_store['repository']}",
                          data=query,
                          params=params,
                          auth=(triple_store['username'], triple_store['password']),
                          headers=headers))
    except (ConnectionError, OSError):
        raise


def add_graph_to_params(params: dict, graph: Literal) -> dict:
    graph = graph or "http://rdf4j.org/schema/rdf4j#nil"
    if params:
        params['default-graph-uri'] = graph
        params['using-graph-uri'] = graph
        params['remove-graph-uri'] = graph
        params['insert-graph-uri'] = graph
    else:
        params = {
            'default-graph-uri': graph,
            'using-graph-uri': graph,
            'remove-graph-uri': graph,
            'insert-graph-uri': graph
        }
    return params
