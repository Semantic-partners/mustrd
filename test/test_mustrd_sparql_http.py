"""Request building for stores addressed over the SPARQL 1.1 protocols.

The live suites prove the backend works — scripts/fuseki_integration.sh in CI, and
scripts/tentris_integration.sh against a local Tentris. These pin the decisions
that were wrong at some point while writing it, so a regression shows up in the
ordinary suite rather than only when a server is running.

Everything here is standard SPARQL 1.1. The per-store differences are two: where
the endpoints sit, and whether a CONSTRUCT can return quads.
"""
from unittest.mock import patch

import pytest
from rdflib import Graph, Literal, URIRef

from mustrd import mustrdFuseki, mustrdSparqlHttp, mustrdTentris
from mustrd.spec_component import UpdatableDataset

FUSEKI = mustrdFuseki.BACKEND
TENTRIS = mustrdTentris.BACKEND

FUSEKI_TS = {"url": "http://localhost", "port": "3030", "dataset": "ds"}
TENTRIS_TS = {"url": "http://127.0.0.1", "port": "9080"}

TRIPLES = '<https://a.example/s> <https://a.example/p> "o" .'
QUADS = '<https://a.example/g> { <https://a.example/s> <https://a.example/p> "o" . }'


class _FakeResponse:
    def __init__(self, status_code=200, content=b""):
        self.status_code = status_code
        self.content = content


def a_dataset(data: str, fmt: str) -> UpdatableDataset:
    dataset = UpdatableDataset(default_union=True)
    dataset.parse(data=data, format=fmt)
    return dataset


# ---------------------------------------------------------------------------
# Where the endpoints sit. This is most of what separates one store from another.
# ---------------------------------------------------------------------------
def test_fuseki_endpoints_sit_under_the_dataset_name():
    assert FUSEKI.url(FUSEKI_TS, "query") == "http://localhost:3030/ds/sparql"
    assert FUSEKI.url(FUSEKI_TS, "update") == "http://localhost:3030/ds/update"
    assert FUSEKI.url(FUSEKI_TS, "graph_store") == "http://localhost:3030/ds/data"


def test_tentris_endpoints_sit_at_the_root():
    # No dataset name: a server serves the one datastore it was started with.
    assert TENTRIS.url(TENTRIS_TS, "query") == "http://127.0.0.1:9080/sparql"
    assert TENTRIS.url(TENTRIS_TS, "update") == "http://127.0.0.1:9080/update"
    assert TENTRIS.url(TENTRIS_TS, "graph_store") == "http://127.0.0.1:9080/graph-store"


def test_a_url_without_a_port_is_left_alone():
    assert TENTRIS.url({"url": "https://tentris.example"}, "query") \
        == "https://tentris.example/sparql"


def test_a_trailing_slash_does_not_double_up():
    assert TENTRIS.url({"url": "https://tentris.example/"}, "query") \
        == "https://tentris.example/sparql"


# ---------------------------------------------------------------------------
# Quads on the way out of a CONSTRUCT: a store capability, not a preference.
# ---------------------------------------------------------------------------
def test_fuseki_asks_a_construct_for_trig():
    # ARQ extends the CONSTRUCT grammar to allow GRAPH in the template, so a
    # construct can return quads and Turtle would discard the graph names.
    assert FUSEKI.construct_accept == "application/trig"


def test_tentris_asks_a_construct_for_turtle():
    # Standard SPARQL 1.1: a CONSTRUCT template is triple patterns only, so there
    # are no graph names to keep — and asking for TriG is a 406.
    assert TENTRIS.construct_accept == "text/turtle"


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
def test_no_auth_when_none_is_configured():
    # A store may serve its endpoints unauthenticated; an empty credential pair
    # turns that into a 401.
    assert TENTRIS.auth(TENTRIS_TS) is None


def test_basic_auth_when_configured():
    assert TENTRIS.auth({**TENTRIS_TS, "username": "u", "password": "p"}) == ("u", "p")


# ---------------------------------------------------------------------------
# upload_given
# ---------------------------------------------------------------------------
def _capture_upload(given, triple_store=None, backend=TENTRIS):
    calls = {"updates": [], "puts": []}

    def fake_post(url, data=None, params=None, auth=None, headers=None):
        calls["updates"].append(data.decode("utf-8"))
        return _FakeResponse(200)

    def fake_put(url, data=None, params=None, auth=None, headers=None):
        calls["puts"].append({"url": url, "params": params, "data": data,
                              "headers": headers})
        return _FakeResponse(200)

    store = dict(triple_store or TENTRIS_TS)
    with patch.object(mustrdSparqlHttp.requests, "post", side_effect=fake_post), \
         patch.object(mustrdSparqlHttp.requests, "put", side_effect=fake_put):
        backend.upload_given(store, given)
    return calls, store


def test_the_store_is_emptied_before_the_given_is_loaded():
    # Without this a spec inherits what the spec before it left behind: a Graph
    # Store PUT replaces one graph and leaves the rest, so a triples-only spec
    # after a quad-given spec still sees the quads. Passes alone, fails in a suite.
    calls, _ = _capture_upload(a_dataset(TRIPLES, "turtle"))

    assert calls["updates"] == ["DROP ALL"]


def test_each_graph_is_put_separately_as_turtle():
    # One PUT per graph is what the Graph Store Protocol defines. A whole-dataset
    # TriG PUT is not, and a store that keeps to the spec rejects it.
    calls, store = _capture_upload(a_dataset(QUADS, "trig"))

    assert len(calls["puts"]) == 1
    put = calls["puts"][0]
    assert put["params"] == {"graph": "https://a.example/g"}
    assert put["headers"]["Content-Type"] == "text/turtle"
    assert store["dataset_graphs"] == ["https://a.example/g"]


def test_a_triples_given_goes_to_the_configured_input_graph():
    calls, store = _capture_upload(
        a_dataset(TRIPLES, "turtle"),
        {**TENTRIS_TS, "input_graph": URIRef("https://a.example/in")})

    assert calls["puts"][0]["params"] == {"graph": "https://a.example/in"}
    assert store["dataset_graphs"] == ["https://a.example/in"]


def test_a_triples_given_with_no_input_graph_goes_to_the_default_graph():
    calls, store = _capture_upload(a_dataset(TRIPLES, "turtle"))

    assert calls["puts"][0]["params"] == {"default": ""}
    # Nothing to declare: an unqualified query already reads the default graph.
    assert store["dataset_graphs"] == []


def test_a_plain_graph_uploads_like_any_other_given():
    # A flat Graph, not a Dataset — upload must not assume quads.
    calls, store = _capture_upload(Graph().parse(data=TRIPLES, format="turtle"))

    assert calls["puts"][0]["headers"]["Content-Type"] == "text/turtle"
    assert store["dataset_graphs"] == []


def test_no_given_makes_no_request():
    with patch.object(mustrdSparqlHttp.requests, "put") as put, \
         patch.object(mustrdSparqlHttp.requests, "post") as post:
        TENTRIS.upload_given(dict(TENTRIS_TS), None)
    put.assert_not_called()
    post.assert_not_called()


# ---------------------------------------------------------------------------
# Dataset parameters. Without these an unqualified query reads the store's own
# default graph and a given in a named graph matches nothing.
# ---------------------------------------------------------------------------
def test_a_query_declares_the_graphs_the_given_occupies():
    store = {**TENTRIS_TS, "dataset_graphs": ["https://a.example/g"]}

    assert TENTRIS.dataset_params(store) == {
        "default-graph-uri": ["https://a.example/g"],
        "named-graph-uri": ["https://a.example/g"]}


def test_an_update_uses_the_using_parameters_instead():
    store = {**TENTRIS_TS, "dataset_graphs": ["https://a.example/g"]}

    assert TENTRIS.dataset_params(store, using=True) == {
        "using-graph-uri": ["https://a.example/g"],
        "using-named-graph-uri": ["https://a.example/g"]}


def test_no_parameters_when_the_given_is_in_the_default_graph():
    assert TENTRIS.dataset_params({**TENTRIS_TS, "dataset_graphs": []}) == {}


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------
def _capture_post(call, body=b"", backend=TENTRIS):
    captured = {}

    def fake_post(url, data=None, params=None, auth=None, headers=None):
        captured.update(url=url, data=data, params=params, headers=headers)
        return _FakeResponse(200, body)

    with patch.object(mustrdSparqlHttp.requests, "post", side_effect=fake_post):
        result = call()
    return result, captured


def test_an_ask_reads_the_boolean_from_sparql_results_json():
    result, captured = _capture_post(
        lambda: TENTRIS.execute_ask(dict(TENTRIS_TS), "ASK {}"),
        b'{"head":{},"boolean":true}')

    assert result is True
    assert captured["headers"]["Accept"] == "application/sparql-results+json"


def test_an_ask_answering_false_is_false():
    result, _ = _capture_post(
        lambda: TENTRIS.execute_ask(dict(TENTRIS_TS), "ASK {}"),
        b'{"head":{},"boolean":false}')

    assert result is False


def test_a_response_without_a_boolean_is_a_clear_error():
    with pytest.raises(ValueError, match="boolean"):
        _capture_post(lambda: TENTRIS.execute_ask(dict(TENTRIS_TS), "ASK {}"),
                      b'{"head":{},"results":{"bindings":[]}}')


def test_an_auth_failure_is_reported_as_such():
    from requests import HTTPError

    with patch.object(mustrdSparqlHttp.requests, "post",
                      side_effect=lambda **kw: _FakeResponse(401, b"")):
        with pytest.raises(HTTPError, match="Tentris authentication error"):
            TENTRIS.execute_select(dict(TENTRIS_TS), "SELECT * WHERE {?s ?p ?o}")


def test_the_label_names_the_store_in_an_error():
    from requests import HTTPError

    with patch.object(mustrdSparqlHttp.requests, "post",
                      side_effect=lambda **kw: _FakeResponse(401, b"")):
        with pytest.raises(HTTPError, match="Fuseki authentication error"):
            FUSEKI.execute_select(dict(FUSEKI_TS), "SELECT * WHERE {?s ?p ?o}")


# ---------------------------------------------------------------------------
# Bindings
# ---------------------------------------------------------------------------
def test_bindings_become_a_values_clause_not_a_substitution():
    # Substituting `?o` throughout also rewrites the SELECT projection, and the
    # server then names the column after the expression rather than the variable.
    bound = mustrdSparqlHttp.bound(
        "SELECT ?s ?p ?o WHERE {?s ?p ?o}", {"o": Literal("hello")})

    assert "SELECT ?s ?p ?o" in bound
    assert 'VALUES ?o {"hello"}' in bound


def test_no_bindings_leaves_the_query_alone():
    query = "SELECT * WHERE {?s ?p ?o}"

    assert mustrdSparqlHttp.bound(query, None) == query


# ---------------------------------------------------------------------------
# Reading the store back after an update
# ---------------------------------------------------------------------------
def _capture_read(default_graph: bytes, named: bytes, backend=TENTRIS):
    bodies = [default_graph, named]

    def fake_post(url, data=None, params=None, auth=None, headers=None):
        return _FakeResponse(200, bodies.pop(0))

    with patch.object(mustrdSparqlHttp.requests, "post", side_effect=fake_post):
        return backend.read_dataset(dict(TENTRIS_TS))


NAMED_ROW = (b'{"head":{"vars":["g","s","p","o"]},"results":{"bindings":[{'
             b'"g":{"type":"uri","value":"https://a.example/g"},'
             b'"s":{"type":"uri","value":"https://a.example/s"},'
             b'"p":{"type":"uri","value":"https://a.example/p"},'
             b'"o":{"type":"literal","value":"o"}}]}}')
NO_ROWS = b'{"head":{"vars":["g","s","p","o"]},"results":{"bindings":[]}}'


def test_the_read_back_keeps_the_graph_each_triple_sits_in():
    # Two standard queries rather than one convenient non-standard one: a TriG
    # Graph Store GET, or a CONSTRUCT naming graphs, are each a single request but
    # neither is SPARQL 1.1.
    result = _capture_read(b"", NAMED_ROW)

    assert {str(g.identifier) for g in result.graphs() if len(g)} \
        == {"https://a.example/g"}


def test_the_read_back_includes_the_default_graph():
    result = _capture_read(TRIPLES.encode(), NO_ROWS)

    assert len(result) == 1


def test_an_empty_store_reads_back_as_empty_not_as_an_error():
    assert len(_capture_read(b"", NO_ROWS)) == 0


def test_the_read_back_is_not_narrowed_to_the_given_s_graphs():
    # It reads the store, not the slice a spec's `given` occupies — an update may
    # have written somewhere the given never mentioned.
    seen = []

    def fake_post(url, data=None, params=None, auth=None, headers=None):
        seen.append(params)
        return _FakeResponse(200, NO_ROWS if b"SELECT" in data else b"")

    store = {**TENTRIS_TS, "dataset_graphs": ["https://a.example/g"]}
    with patch.object(mustrdSparqlHttp.requests, "post", side_effect=fake_post):
        TENTRIS.read_dataset(store)

    assert seen == [{}, {}]


# ---------------------------------------------------------------------------
# Terms out of SPARQL Results JSON
# ---------------------------------------------------------------------------
def test_a_typed_literal_keeps_its_datatype():
    term = mustrdSparqlHttp.term_of(
        {"type": "literal", "value": "1",
         "datatype": "http://www.w3.org/2001/XMLSchema#integer"})

    assert term.datatype == URIRef("http://www.w3.org/2001/XMLSchema#integer")


def test_a_language_tagged_literal_keeps_its_tag():
    term = mustrdSparqlHttp.term_of(
        {"type": "literal", "value": "hello", "xml:lang": "en"})

    assert term.language == "en"


def test_a_uri_binding_is_a_uriref():
    assert mustrdSparqlHttp.term_of(
        {"type": "uri", "value": "https://a.example/s"}) == URIRef("https://a.example/s")
