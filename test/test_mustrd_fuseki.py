"""The Fuseki backend's request building, without a server.

The live suite (scripts/fuseki_integration.sh) is what proves the backend works;
these pin the decisions that were wrong at some point during writing it, so a
regression shows up in the ordinary suite rather than only when a container is
running.
"""
from unittest.mock import patch

import pytest
from rdflib import Graph, URIRef

from mustrd import mustrdFuseki
from mustrd.spec_component import UpdatableDataset, parse_into_dataset

TS = {"url": "http://localhost", "port": "3030", "dataset": "ds"}
TRIPLES = '<https://a.example/s> <https://a.example/p> "o" .'
QUADS = '<https://a.example/g> { <https://a.example/s> <https://a.example/p> "o" . }'


class _FakeResponse:
    def __init__(self, status_code=200, content=b""):
        self.status_code = status_code
        self.content = content


def _graph_names(payload: bytes) -> set:
    """The named graphs in a TriG payload, as the server would read them."""
    parsed = UpdatableDataset(default_union=True)
    parse_into_dataset(parsed, payload.decode("utf-8"), "trig")
    return {str(g.identifier) for g in parsed.graphs()
            if len(g) and str(g.identifier) != "urn:x-rdflib:default"}


def a_dataset(data: str, fmt: str) -> UpdatableDataset:
    dataset = UpdatableDataset(default_union=True)
    dataset.parse(data=data, format=fmt)
    return dataset


# ---------------------------------------------------------------------------
# URLs and auth
# ---------------------------------------------------------------------------
def test_endpoints_come_from_the_dataset_name():
    assert mustrdFuseki._dataset_url(TS, "sparql") == "http://localhost:3030/ds/sparql"
    assert mustrdFuseki._dataset_url(TS, "update") == "http://localhost:3030/ds/update"
    assert mustrdFuseki._dataset_url(TS, "data") == "http://localhost:3030/ds/data"


def test_a_url_without_a_port_is_left_alone():
    assert mustrdFuseki._dataset_url(
        {"url": "https://fuseki.example", "dataset": "ds"}, "sparql") \
        == "https://fuseki.example/ds/sparql"


def test_no_auth_header_when_none_configured():
    # A stock Fuseki serves its dataset endpoints unauthenticated. Sending an
    # empty basic-auth tuple would turn that into a 401.
    assert mustrdFuseki._auth(TS) is None


def test_basic_auth_when_configured():
    assert mustrdFuseki._auth({**TS, "username": "u", "password": "p"}) == ("u", "p")


# ---------------------------------------------------------------------------
# upload_given: always a whole-dataset replace
# ---------------------------------------------------------------------------
def _capture_put(given, triple_store=None):
    captured = {}

    def fake_put(url, data=None, params=None, auth=None, headers=None):
        captured.update(url=url, data=data, params=params, headers=headers)
        return _FakeResponse(200)

    store = dict(triple_store or TS)
    with patch.object(mustrdFuseki.requests, "put", side_effect=fake_put):
        mustrdFuseki.upload_given(store, given)
    return captured, store


def test_a_given_is_put_to_the_dataset_endpoint_as_trig():
    # Not a per-graph PUT. A PUT to one graph leaves the others untouched, so a
    # triples-only spec would inherit the named graphs of whichever quad-given
    # spec ran before it — green alone, red in a suite.
    captured, _ = _capture_put(a_dataset(TRIPLES, "turtle"))

    assert captured["url"].endswith("/ds/data")
    assert captured["headers"]["Content-Type"] == "application/trig"


def test_a_quad_given_keeps_its_own_graphs():
    captured, store = _capture_put(a_dataset(QUADS, "trig"))

    # Parsed back rather than string-matched: the payload uses prefixes, so the
    # full IRI is not literally present in it.
    assert _graph_names(captured["data"]) == {"https://a.example/g"}
    assert store["dataset_graphs"] == ["https://a.example/g"]


def test_a_triples_given_goes_to_the_configured_input_graph():
    captured, store = _capture_put(
        a_dataset(TRIPLES, "turtle"), {**TS, "input_graph": URIRef("https://a.example/in")})

    assert _graph_names(captured["data"]) == {"https://a.example/in"}
    assert store["dataset_graphs"] == ["https://a.example/in"]


def test_a_triples_given_with_no_input_graph_goes_to_the_default_graph():
    _, store = _capture_put(a_dataset(TRIPLES, "turtle"))

    # No named graph to declare, so no dataset parameters are needed either: an
    # unqualified query already reads the default graph.
    assert store["dataset_graphs"] == []


def test_no_given_makes_no_request():
    with patch.object(mustrdFuseki.requests, "put") as put:
        mustrdFuseki.upload_given(dict(TS), None)
    put.assert_not_called()


# ---------------------------------------------------------------------------
# Dataset parameters. Without these an unqualified query reads the dataset's
# default graph and a given in a named graph matches nothing.
# ---------------------------------------------------------------------------
def test_a_query_declares_the_graphs_the_given_occupies():
    store = {**TS, "dataset_graphs": ["https://a.example/g"]}

    params = mustrdFuseki._dataset_params(store)

    assert params == {"default-graph-uri": ["https://a.example/g"],
                      "named-graph-uri": ["https://a.example/g"]}


def test_an_update_uses_the_using_parameters_instead():
    store = {**TS, "dataset_graphs": ["https://a.example/g"]}

    assert mustrdFuseki._dataset_params(store, using=True) == {
        "using-graph-uri": ["https://a.example/g"],
        "using-named-graph-uri": ["https://a.example/g"]}


def test_no_parameters_when_the_given_is_in_the_default_graph():
    assert mustrdFuseki._dataset_params({**TS, "dataset_graphs": []}) == {}


# ---------------------------------------------------------------------------
# Accept headers
# ---------------------------------------------------------------------------
def _capture_post(call, body=b""):
    captured = {}

    def fake_post(url, data=None, params=None, auth=None, headers=None):
        captured.update(url=url, data=data, headers=headers)
        return _FakeResponse(200, body)

    with patch.object(mustrdFuseki.requests, "post", side_effect=fake_post):
        result = call()
    return result, captured


def test_a_construct_asks_for_trig():
    # Jena's CONSTRUCT can produce quads, so Turtle would discard graph names.
    _, captured = _capture_post(
        lambda: mustrdFuseki.execute_construct(dict(TS), "CONSTRUCT {?s ?p ?o} WHERE {?s ?p ?o}"),
        QUADS.encode())

    assert captured["headers"]["Accept"] == "application/trig"


def test_a_construct_keeps_the_named_graphs():
    result, _ = _capture_post(
        lambda: mustrdFuseki.execute_construct(dict(TS), "CONSTRUCT {?s ?p ?o} WHERE {?s ?p ?o}"),
        QUADS.encode())

    assert "https://a.example/g" in {str(g.identifier) for g in result.graphs()}


def test_an_ask_reads_the_boolean_from_sparql_results_json():
    result, captured = _capture_post(
        lambda: mustrdFuseki.execute_ask(dict(TS), "ASK {}"),
        b'{"head":{},"boolean":true}')

    assert result is True
    assert captured["headers"]["Accept"] == "application/sparql-results+json"


def test_an_ask_answering_false_is_false_not_falsy_noise():
    result, _ = _capture_post(
        lambda: mustrdFuseki.execute_ask(dict(TS), "ASK {}"),
        b'{"head":{},"boolean":false}')

    assert result is False


def test_a_response_without_a_boolean_is_a_clear_error():
    with pytest.raises(ValueError, match="boolean"):
        _capture_post(lambda: mustrdFuseki.execute_ask(dict(TS), "ASK {}"),
                      b'{"head":{},"results":{"bindings":[]}}')


# ---------------------------------------------------------------------------
# Bindings
# ---------------------------------------------------------------------------
def test_bindings_become_a_values_clause_not_a_substitution():
    # Substituting `?o` throughout also rewrites the SELECT projection, and the
    # endpoint then names the column after the expression — Fuseki returns `.0`.
    from rdflib import Literal

    bound = mustrdFuseki._bound(
        "SELECT ?s ?p ?o WHERE {?s ?p ?o}", {"o": Literal("hello")})

    assert "SELECT ?s ?p ?o" in bound
    assert 'VALUES ?o {"hello"}' in bound


def test_no_bindings_leaves_the_query_alone():
    query = "SELECT * WHERE {?s ?p ?o}"

    assert mustrdFuseki._bound(query, None) == query


# ---------------------------------------------------------------------------
# Read-back
# ---------------------------------------------------------------------------
def test_the_dataset_is_read_back_over_the_graph_store_protocol():
    captured = {}

    def fake_get(url, auth=None, headers=None):
        captured.update(url=url, headers=headers)
        return _FakeResponse(200, QUADS.encode())

    with patch.object(mustrdFuseki.requests, "get", side_effect=fake_get):
        result = mustrdFuseki.read_dataset(dict(TS))

    # GSP GET, not a CONSTRUCT: no dataset parameters to get wrong, and it cannot
    # miss a graph the query forgot to mention.
    assert captured["url"].endswith("/ds/data")
    assert captured["headers"]["Accept"] == "application/trig"
    assert "https://a.example/g" in {str(g.identifier) for g in result.graphs()}


def test_an_empty_dataset_reads_back_as_empty_not_as_an_error():
    with patch.object(mustrdFuseki.requests, "get",
                      side_effect=lambda **kw: _FakeResponse(200, b"")):
        assert len(mustrdFuseki.read_dataset(dict(TS))) == 0


def test_an_auth_failure_is_reported_as_such():
    from requests import HTTPError

    with patch.object(mustrdFuseki.requests, "post",
                      side_effect=lambda **kw: _FakeResponse(401, b"")):
        with pytest.raises(HTTPError, match="Fuseki authentication error"):
            mustrdFuseki.execute_select(dict(TS), "SELECT * WHERE {?s ?p ?o}")


def test_a_graph_only_a_plain_graph_still_uploads():
    # A `then`-style flat Graph, not a Dataset — upload must not assume quads.
    captured, store = _capture_put(Graph().parse(data=TRIPLES, format="turtle"))

    assert captured["headers"]["Content-Type"] == "application/trig"
    assert store["dataset_graphs"] == []
