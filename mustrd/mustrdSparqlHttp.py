"""One backend for any store that speaks the SPARQL 1.1 protocols over HTTP.

Fuseki and Tentris both do, and they differ only in where the endpoints sit and
whether CONSTRUCT can return quads. Everything that was hard — isolating one
spec's data from the next, getting bindings past the SELECT projection, making an
unqualified query see a `given` that lives in a named graph — is the same problem
for both, so it is solved once here rather than once per product.

Three protocols:

* query        SPARQL 1.1 Query Protocol
* update       SPARQL 1.1 Update Protocol
* graph store  SPARQL 1.1 Graph Store HTTP Protocol

Everything below is standard SPARQL 1.1. No vendor extension is required, which is
the point: a store that implements the specs works without a module of its own.
The one place a product may differ is whether its CONSTRUCT can name graphs —
Jena extends the grammar for that, and `construct_accept` is where a backend says
so.
"""
import json
import logging

import requests
from rdflib import Dataset, Graph, URIRef
from rdflib.graph import DATASET_DEFAULT_GRAPH_ID
from requests import ConnectionError, Response

from .spec_component import UpdatableDataset, parse_into_dataset
from .utils import (manage_http_response, query_with_bindings,
                    rdflib_internals_quiet, sparql_ask_answer)

log = logging.getLogger(__name__)

RESULTS_JSON = "application/sparql-results+json"


class SparqlHttpBackend:
    """A store addressed over the SPARQL 1.1 protocols.

    `paths` maps "query", "update" and "graph_store" to a function of the triple
    store config returning the path under the base URL, because products lay them
    out differently: Fuseki puts them under a dataset name, Tentris serves them at
    the root.

    `construct_accept` is the media type a CONSTRUCT asks for. TriG where the
    store can return quads, Turtle where it cannot — asking for TriG from a store
    that only offers Turtle is a 406, and asking for Turtle from one that could
    have given quads discards the graph names.
    """

    def __init__(self, label: str, paths: dict, construct_accept: str = "text/turtle"):
        self.label = label
        self.paths = paths
        self.construct_accept = construct_accept

    # -- plumbing ---------------------------------------------------------
    def manage_response(self, response: Response) -> str:
        return manage_http_response(
            response, self.label,
            success_codes=(200, 201, 204), auth_codes=(401, 403),
            http_error_codes=(406,))

    def url(self, triple_store: dict, service: str) -> str:
        base = str(triple_store["url"]).rstrip("/")
        port = triple_store.get("port")
        if port:
            base = f"{base}:{port}"
        return base + self.paths[service](triple_store)

    def auth(self, triple_store: dict):
        """Basic auth only when configured.

        A stock server may serve its endpoints unauthenticated; sending an empty
        credential pair turns that into a 401.
        """
        username = triple_store.get("username")
        password = triple_store.get("password")
        return (str(username), str(password)) if username and password else None

    # -- the given --------------------------------------------------------
    def upload_given(self, triple_store: dict, given: Graph):
        """Empty the store, then load `given` one graph at a time.

        `DROP ALL` first. Without it a spec inherits whatever the spec before it
        left behind: a Graph Store PUT replaces one graph and leaves every other
        graph in place, so a triples-only spec running after a quad-given spec
        still sees the quads. That passes alone and fails in a suite.

        One PUT per graph, Turtle, rather than one PUT of the whole dataset as
        TriG. The per-graph form is what the Graph Store Protocol defines and
        every store here accepts; the whole-dataset TriG form is not.

        Which graphs the data landed in is recorded on `triple_store`, because a
        query has to say so — see `dataset_params`.
        """
        if given is None:
            return
        try:
            self.post_update_raw(triple_store, "DROP ALL")
            graphs = []
            for name, graph in self.graphs_to_load(given, triple_store.get("input_graph")):
                self.put_graph(triple_store, name, graph)
                if name:
                    graphs.append(str(name))
            triple_store["dataset_graphs"] = graphs
        except (ConnectionError, OSError):
            raise

    def graphs_to_load(self, given: Graph, input_graph):
        """`(graph name or None, graph)` pairs to PUT.

        A quad `given` keeps its own graphs. A triples-only `given` goes to the
        configured input graph, or to the default graph when none is configured —
        where an unqualified query finds it with no dataset parameter at all.
        """
        named = [g for g in graphs_of(given)
                 if len(g) and str(g.identifier) != str(DATASET_DEFAULT_GRAPH_ID)]
        if named:
            return [(g.identifier, g) for g in named]

        flat = Graph()
        for triple in given.triples((None, None, None)):
            flat.add(triple)
        for prefix, namespace in given.namespaces():
            flat.bind(prefix, namespace)
        return [(URIRef(str(input_graph)) if input_graph else None, flat)]

    def put_graph(self, triple_store: dict, name, graph: Graph):
        params = {"graph": str(name)} if name else {"default": ""}
        self.manage_response(requests.put(
            url=self.url(triple_store, "graph_store"),
            params=params,
            data=graph.serialize(format="ttl").encode("utf-8"),
            auth=self.auth(triple_store),
            headers={"Content-Type": "text/turtle"}))

    # -- dataset selection ------------------------------------------------
    def dataset_params(self, triple_store: dict, using: bool = False) -> dict:
        """The graphs a query or update should read, as protocol parameters.

        Every graph the `given` occupies is offered both as the default graph and
        as a named graph, so one spec works whether or not its query names a
        graph. Without this an unqualified pattern reads the store's own default
        graph and a `given` in a named graph matches nothing.

        Empty when the `given` went to the default graph, where an unqualified
        query already finds it.
        """
        graphs = triple_store.get("dataset_graphs") or []
        if not graphs:
            return {}
        if using:
            return {"using-graph-uri": graphs, "using-named-graph-uri": graphs}
        return {"default-graph-uri": graphs, "named-graph-uri": graphs}

    # -- requests ---------------------------------------------------------
    def post_query(self, triple_store: dict, query: str, accept: str) -> str:
        try:
            return self.manage_response(requests.post(
                url=self.url(triple_store, "query"),
                data=query.encode("utf-8"),
                params=self.dataset_params(triple_store),
                auth=self.auth(triple_store),
                headers={"Content-Type": "application/sparql-query", "Accept": accept}))
        except (ConnectionError, OSError):
            raise

    def post_update_raw(self, triple_store: dict, query: str) -> str:
        try:
            return self.manage_response(requests.post(
                url=self.url(triple_store, "update"),
                data=query.encode("utf-8"),
                params=self.dataset_params(triple_store, using=True),
                auth=self.auth(triple_store),
                headers={"Content-Type": "application/sparql-update"}))
        except (ConnectionError, OSError):
            raise

    # -- the four operations mustrd dispatches ----------------------------
    def execute_select(self, triple_store: dict, when: str, bindings: dict = None) -> str:
        return self.post_query(triple_store, bound(when, bindings), RESULTS_JSON)

    def execute_ask(self, triple_store: dict, when: str, bindings: dict = None) -> bool:
        return sparql_ask_answer(
            self.post_query(triple_store, bound(when, bindings), RESULTS_JSON))

    def execute_construct(self, triple_store: dict, when: str, bindings: dict = None) -> Dataset:
        quads = UpdatableDataset(default_union=True)
        body = self.post_query(triple_store, bound(when, bindings), self.construct_accept)
        if body:
            parse_into_dataset(
                quads, body,
                "trig" if self.construct_accept == "application/trig" else "turtle")
        return quads

    def execute_update(self, triple_store: dict, when: str, bindings: dict = None) -> Dataset:
        """Run the update, then read the whole store back.

        Read back rather than trusting the update, because a `then` is compared
        against what the store now holds — including graphs the update never
        mentioned.
        """
        self.post_update_raw(triple_store, bound(when, bindings))
        return self.read_dataset(triple_store)

    # -- reading everything back ------------------------------------------
    def read_dataset(self, triple_store: dict) -> Dataset:
        """Every triple in the store, with the graph each one sits in.

        Two standard queries rather than one convenient non-standard one. A Graph
        Store GET of the whole dataset as TriG, or a CONSTRUCT with GRAPH in the
        template, would each do this in a single request — but neither is SPARQL
        1.1, and a store that implements only the specs rejects both. A CONSTRUCT
        for the default graph plus a SELECT for the named ones works anywhere.

        No dataset parameters: this reads the store, not the slice a spec's
        `given` occupies.
        """
        quads = UpdatableDataset(default_union=True)
        unrestricted = {k: v for k, v in triple_store.items() if k != "dataset_graphs"}

        default_graph = self.post_query(
            unrestricted, "CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o }", "text/turtle")
        if default_graph:
            with rdflib_internals_quiet():
                quads.default_graph.parse(data=default_graph, format="turtle")

        named = self.post_query(
            unrestricted,
            "SELECT ?g ?s ?p ?o WHERE { GRAPH ?g { ?s ?p ?o } }", RESULTS_JSON)
        for row in json.loads(named)["results"]["bindings"]:
            quads.get_context(URIRef(row["g"]["value"])).add(
                (term_of(row["s"]), term_of(row["p"]), term_of(row["o"])))
        return quads


def graphs_of(given: Graph):
    """The graphs in `given`; a plain Graph counts as none."""
    if not isinstance(given, Dataset):
        return []
    with rdflib_internals_quiet():
        return list(given.graphs())


def term_of(binding: dict):
    """An RDF term from one SPARQL Results JSON binding."""
    from rdflib import BNode, Literal

    kind = binding["type"]
    if kind == "uri":
        return URIRef(binding["value"])
    if kind == "bnode":
        return BNode(binding["value"])
    return Literal(
        binding["value"],
        lang=binding.get("xml:lang"),
        datatype=URIRef(binding["datatype"]) if binding.get("datatype") else None)


def bound(when: str, bindings: dict = None) -> str:
    return query_with_bindings(bindings, when) if bindings else when
