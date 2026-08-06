"""Stardog execution backend for mustrd.

Talks to a Stardog server over its HTTP SPARQL protocol
(https://docs.stardog.com/query-stardog/#http-and-sparql-protocols).

Two things set this backend apart from the GraphDb/Anzo ones:

* Authentication prefers a bearer token (``Authorization: Bearer <token>``) and
  falls back to HTTP basic auth when no token is configured.
* The dataset a query runs over is an explicit *combination* of named graphs:
  the ``inputGraph`` the test's ``given`` data is loaded into, plus any number
  of additional materialised graphs and virtual graphs declared on the triple
  store config. That lets the *same* query be tested against different mixes of
  materialised and virtualised data just by pointing it at different configs.
"""
import urllib.parse
import logging

import requests
from rdflib import Graph
from requests import ConnectionError, Response

from .utils import manage_http_response

log = logging.getLogger(__name__)


def _base_url(triple_store: dict) -> str:
    """Server base URL, appending the port when it is configured separately."""
    url = str(triple_store["url"]).rstrip("/")
    port = triple_store.get("port")
    if port:
        url = f"{url}:{port}"
    return url


def _auth_and_headers(triple_store: dict, extra_headers: dict = None):
    """Return (auth, headers) for a request.

    A bearer token wins when present; otherwise fall back to basic auth so
    Stardog instances configured either way keep working.
    """
    headers = dict(extra_headers or {})
    auth = None
    token = triple_store.get("token")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    elif triple_store.get("username") is not None:
        auth = (triple_store["username"], triple_store["password"])
    return auth, headers


# https://docs.stardog.com/operating-stardog/server-administration/server-monitoring#http-status-codes
def manage_stardog_response(response: Response) -> str:
    return manage_http_response(
        response, "Stardog",
        success_codes=(200, 201, 204), auth_codes=(401, 403))


def dataset_graphs(triple_store: dict) -> list:
    """The named graphs a query should run over, in declared order without dupes.

    inputGraph (where ``given`` is loaded) first, then the materialised graphs,
    then the virtual graphs. Empty means "let the server decide" (its default
    graph), matching a config that declares no graphs at all.
    """
    graphs = []
    for key in ("input_graph", "materialised_graphs", "virtual_graphs"):
        value = triple_store.get(key)
        if not value:
            continue
        if isinstance(value, (list, tuple)):
            graphs.extend(str(g) for g in value)
        else:
            graphs.append(str(value))
    seen = set()
    ordered = []
    for g in graphs:
        if g not in seen:
            seen.add(g)
            ordered.append(g)
    return ordered


def query_with_bindings(bindings: dict, when: str) -> str:
    """Inline bindings as VALUES clauses, so any endpoint honours them."""
    values = ""
    for key, value in bindings.items():
        values += f"VALUES ?{key} {{{value.n3()}}}\n"
    where_index = when.lower().find("where {")
    if where_index == -1:
        raise ValueError("No WHERE clause found in the query to bind values to.")
    split_query = [when[:where_index], when[where_index + 7:]]
    return f"{split_query[0].strip()} WHERE {{\n{values}{split_query[1].strip()}"


def upload_given(triple_store: dict, given: Graph):
    """Load the ``given`` data into the materialised inputGraph (PUT replaces it).

    Uses the SPARQL 1.1 Graph Store Protocol, so a PUT drops whatever the graph
    held and stores the payload (https://www.w3.org/TR/sparql11-http-rdf-update/#http-put).
    """
    if given is None:
        return
    try:
        graph = "default"
        if triple_store.get("input_graph"):
            graph = urllib.parse.urlencode({"graph": str(triple_store["input_graph"])})
        url = f"{_base_url(triple_store)}/{triple_store['database']}?{graph}"
        auth, headers = _auth_and_headers(triple_store, {"Content-Type": "text/turtle"})
        manage_stardog_response(requests.put(
            url=url,
            auth=auth,
            data=given.serialize(format="ttl"),
            headers=headers))
    except ConnectionError:
        raise


def execute_select(triple_store: dict, when: str, bindings: dict = None) -> str:
    return post_query(triple_store, when, "application/sparql-results+json", bindings)


def execute_construct(triple_store: dict, when: str, bindings: dict = None) -> Graph:
    return Graph().parse(data=post_query(triple_store, when, "text/turtle", bindings), format="ttl")


def execute_update(triple_store: dict, when: str, bindings: dict = None) -> Graph:
    """Run an update, then read back the resulting state of the dataset graphs.

    The read-back mirrors the GraphDb backend: a CONSTRUCT of everything the
    configured combination of graphs now holds, so an update spec's ``then`` can
    be compared isomorphically against it. Note Stardog has no non-standard
    ``insert-graph-uri``: an unqualified INSERT/DELETE targets the server's
    default graph, so use explicit GRAPH/WITH clauses to write to a named graph.
    """
    if bindings:
        when = query_with_bindings(bindings, when)
    post_update(triple_store, when)
    return execute_construct(triple_store, "CONSTRUCT {?s ?p ?o} WHERE { ?s ?p ?o }")


def post_query(triple_store: dict, query: str, accept: str, bindings: dict = None) -> str:
    if bindings:
        query = query_with_bindings(bindings, query)
    graphs = dataset_graphs(triple_store)
    params = {}
    if graphs:
        # Expose the combination both merged into the default graph and as named
        # graphs, so it works whether the query names graphs or not.
        params["default-graph-uri"] = graphs
        params["named-graph-uri"] = graphs
    url = f"{_base_url(triple_store)}/{triple_store['database']}/query"
    auth, headers = _auth_and_headers(
        triple_store, {"Content-Type": "application/sparql-query", "Accept": accept})
    try:
        return manage_stardog_response(requests.post(
            url=url,
            data=query.encode("utf-8"),
            params=params,
            auth=auth,
            headers=headers))
    except (ConnectionError, OSError):
        raise


def post_update(triple_store: dict, query: str) -> str:
    graphs = dataset_graphs(triple_store)
    params = {}
    if graphs:
        params["using-graph-uri"] = graphs
        params["using-named-graph-uri"] = graphs
    url = f"{_base_url(triple_store)}/{triple_store['database']}/update"
    auth, headers = _auth_and_headers(
        triple_store, {"Content-Type": "application/sparql-update"})
    try:
        return manage_stardog_response(requests.post(
            url=url,
            data=query.encode("utf-8"),
            params=params,
            auth=auth,
            headers=headers))
    except (ConnectionError, OSError):
        raise
