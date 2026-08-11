"""Apache Jena Fuseki execution backend for mustrd.

Fuseki speaks the SPARQL 1.1 protocols with no vendor extensions in the paths
mustrd uses, which makes it the one backend that can be stood up in CI and driven
for real:

* query    ``{url}:{port}/{dataset}/sparql``  (SPARQL 1.1 Query Protocol)
* update   ``{url}:{port}/{dataset}/update``  (SPARQL 1.1 Update Protocol)
* data     ``{url}:{port}/{dataset}/data``    (SPARQL 1.1 Graph Store Protocol)

That matters beyond Fuseki itself. GraphDb, Stardog and Anzo are all only
mock-tested here, because each needs a licence or a server nobody has in CI. The
HTTP request-building, the Accept headers, the response parsing and the
`given`-upload round trip are shared shapes, so exercising them against a real
Fuseki covers the parts of those backends that are not vendor-specific.

Auth is optional: a stock Fuseki serves its dataset endpoints unauthenticated, so
``username``/``password`` are only sent when configured.
"""
import logging

import requests
from rdflib import Dataset, Graph, URIRef
from rdflib.graph import DATASET_DEFAULT_GRAPH_ID
from requests import ConnectionError, Response

from .spec_component import UpdatableDataset, parse_into_dataset
from .utils import (manage_http_response, query_with_bindings,
                    rdflib_internals_quiet, sparql_ask_answer)

log = logging.getLogger(__name__)


def manage_fuseki_response(response: Response) -> str:
    return manage_http_response(
        response, "Fuseki",
        success_codes=(200, 201, 204), auth_codes=(401, 403), http_error_codes=(406,))


def _base_url(triple_store: dict) -> str:
    url = str(triple_store["url"]).rstrip("/")
    port = triple_store.get("port")
    return f"{url}:{port}" if port else url


def _dataset_url(triple_store: dict, service: str) -> str:
    return f"{_base_url(triple_store)}/{triple_store['dataset']}/{service}"


def _auth(triple_store: dict):
    """Basic auth only when configured — a stock Fuseki dataset needs none."""
    username = triple_store.get("username")
    password = triple_store.get("password")
    return (str(username), str(password)) if username and password else None


def upload_given(triple_store: dict, given: Graph):
    """Replace the WHOLE dataset with `given`, over the Graph Store Protocol.

    Always the whole dataset, never a single graph. A PUT to one graph leaves every
    other graph untouched, so a spec whose given is triples-only would inherit the
    named graphs of whichever quad-given spec ran before it — tests that pass alone
    and fail in a suite. Replacing the dataset makes each spec start from exactly
    its own fixture.

    PUT, not POST: the protocol defines PUT as replace
    (https://www.w3.org/TR/sparql11-http-rdf-update/#http-put).

    Which graphs the data landed in is recorded on `triple_store`, because a query
    has to say so: an unqualified pattern reads the dataset's DEFAULT graph, so
    without `default-graph-uri` a given sitting in a named graph matches nothing.
    Same reason the GraphDb and Stardog backends pass their own dataset parameters.
    """
    if given is None:
        return
    try:
        payload, graphs = _as_dataset(given, triple_store.get("input_graph"))
        manage_fuseki_response(requests.put(
            url=_dataset_url(triple_store, "data"),
            data=_as_trig(payload),
            auth=_auth(triple_store),
            headers={"Content-Type": "application/trig"}))
        triple_store["dataset_graphs"] = graphs
    except (ConnectionError, OSError):
        raise


def _as_dataset(given: Graph, input_graph) -> tuple:
    """`given` as a dataset to PUT, and the named graphs it occupies.

    A quad given keeps its own graphs. A triples-only given goes to the configured
    input graph, or the dataset's default graph when none is configured — where an
    unqualified query finds it without any dataset parameter.
    """
    named = _named_graphs(given)
    if named:
        return given, named

    payload = UpdatableDataset(default_union=True)
    target = payload.get_context(URIRef(str(input_graph))) if input_graph \
        else payload.default_graph
    for triple in given.triples((None, None, None)):
        target.add(triple)
    for prefix, namespace in given.namespaces():
        payload.bind(prefix, namespace)
    return payload, ([str(input_graph)] if input_graph else [])


def _as_trig(dataset: Dataset) -> bytes:
    """TriG bytes, without rdflib's own deprecation notices — see
    utils.rdflib_internals_quiet."""
    with rdflib_internals_quiet():
        return dataset.serialize(format="trig").encode("utf-8")


def _named_graphs(given: Graph) -> list:
    """The non-empty named graphs in `given`, or [] if it is only triples."""
    if not isinstance(given, Dataset):
        return []
    return [str(g.identifier) for g in given.graphs()
            if len(g) and str(g.identifier) != str(DATASET_DEFAULT_GRAPH_ID)]


def _dataset_params(triple_store: dict, using: bool = False) -> dict:
    """The graphs a query or update should read, as protocol parameters.

    Every graph the given occupies is offered BOTH as the default graph and as a
    named graph, so the same spec works whether or not its query names a graph —
    the union rdflib gives locally, reproduced over the protocol. Empty when the
    given went to the dataset's own default graph, where an unqualified query
    already finds it.
    """
    graphs = triple_store.get("dataset_graphs") or []
    if not graphs:
        return {}
    if using:
        return {"using-graph-uri": graphs, "using-named-graph-uri": graphs}
    return {"default-graph-uri": graphs, "named-graph-uri": graphs}


def post_query(triple_store: dict, query: str, accept: str) -> str:
    try:
        return manage_fuseki_response(requests.post(
            url=_dataset_url(triple_store, "sparql"),
            data=query.encode("utf-8"),
            params=_dataset_params(triple_store),
            auth=_auth(triple_store),
            headers={"Content-Type": "application/sparql-query", "Accept": accept}))
    except (ConnectionError, OSError):
        raise


def post_update(triple_store: dict, query: str) -> str:
    try:
        return manage_fuseki_response(requests.post(
            url=_dataset_url(triple_store, "update"),
            data=query.encode("utf-8"),
            params=_dataset_params(triple_store, using=True),
            auth=_auth(triple_store),
            headers={"Content-Type": "application/sparql-update"}))
    except (ConnectionError, OSError):
        raise


def read_dataset(triple_store: dict) -> Dataset:
    """The whole dataset — default graph and every named graph — as quads.

    A Graph Store Protocol GET on the dataset endpoint, rather than a CONSTRUCT:
    it needs no dataset parameters and cannot miss a graph the query forgot to
    mention.
    """
    quads = UpdatableDataset(default_union=True)
    try:
        body = manage_fuseki_response(requests.get(
            url=_dataset_url(triple_store, "data"),
            auth=_auth(triple_store),
            headers={"Accept": "application/trig"}))
    except (ConnectionError, OSError):
        raise
    if body:
        parse_into_dataset(quads, body, "trig")
    return quads


def execute_select(triple_store: dict, when: str, bindings: dict = None) -> str:
    return post_query(triple_store, _bound(when, bindings),
                      "application/sparql-results+json")


def execute_ask(triple_store: dict, when: str, bindings: dict = None) -> bool:
    """The boolean from a SPARQL results document.

    SPARQL 1.1 Results JSON puts it under `boolean`
    (https://www.w3.org/TR/sparql11-results-json/#ask-result-form), so the same
    parse works for any store that speaks the protocol.
    """
    return sparql_ask_answer(
        post_query(triple_store, _bound(when, bindings), "application/sparql-results+json"))


def execute_construct(triple_store: dict, when: str, bindings: dict = None) -> Graph:
    """TriG, not Turtle: Jena's CONSTRUCT can produce quads.

    ARQ extends the CONSTRUCT grammar to allow `GRAPH` in the template
    (https://jena.apache.org/documentation/query/construct-quad.html), which is
    what a dry run of an `INSERT { GRAPH ?g … }` relies on. Turtle carries no
    graph names, so asking for it would discard them here.
    """
    quads = UpdatableDataset(default_union=True)
    parse_into_dataset(
        quads, post_query(triple_store, _bound(when, bindings), "application/trig"),
        "trig")
    return quads


def execute_update(triple_store: dict, when: str, bindings: dict = None) -> Dataset:
    """Run the update, then read the whole dataset back.

    Read back over the Graph Store Protocol so an update that wrote to named
    graphs — or to the default graph — is compared against whatever the `then`
    asks for, graph-aware or flat.
    """
    post_update(triple_store, _bound(when, bindings))
    return read_dataset(triple_store)


def _bound(when: str, bindings: dict = None) -> str:
    return query_with_bindings(bindings, when) if bindings else when
