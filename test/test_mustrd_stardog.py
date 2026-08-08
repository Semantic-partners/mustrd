"""Unit tests for the Stardog backend helpers.

These exercise URL/auth/dataset construction without a live Stardog. The
execute_* functions themselves need a running Stardog server, so — like the
Anzo integration tests — they are left to be run against a real instance.
"""
from unittest.mock import patch

import pytest
from rdflib import Graph, Literal, Variable

from mustrd import mustrdStardog


def test_base_url_appends_port_when_separate():
    ts = {"url": "http://localhost", "port": "5820"}
    assert mustrdStardog._base_url(ts) == "http://localhost:5820"


def test_base_url_without_port():
    ts = {"url": "http://localhost:5820/"}
    assert mustrdStardog._base_url(ts) == "http://localhost:5820"


def test_auth_prefers_bearer_token():
    ts = {"token": "abc", "username": "admin", "password": "admin"}
    auth, headers = mustrdStardog._auth_and_headers(ts, {"Accept": "text/turtle"})
    assert auth is None
    assert headers["Authorization"] == "Bearer abc"
    assert headers["Accept"] == "text/turtle"


def test_auth_falls_back_to_basic():
    ts = {"username": "admin", "password": "secret"}
    auth, headers = mustrdStardog._auth_and_headers(ts)
    assert auth == ("admin", "secret")
    assert "Authorization" not in headers


def test_dataset_graphs_combines_materialised_and_virtual_in_order():
    ts = {
        "input_graph": "http://ex/input",
        "materialised_graphs": ["http://ex/mat-1", "http://ex/mat-2"],
        "virtual_graphs": ["virtual://v-1"],
    }
    assert mustrdStardog.dataset_graphs(ts) == [
        "http://ex/input",
        "http://ex/mat-1",
        "http://ex/mat-2",
        "virtual://v-1",
    ]


def test_dataset_graphs_dedupes_preserving_order():
    ts = {
        "input_graph": "http://ex/g",
        "materialised_graphs": ["http://ex/g", "http://ex/other"],
        "virtual_graphs": [],
    }
    assert mustrdStardog.dataset_graphs(ts) == ["http://ex/g", "http://ex/other"]


def test_dataset_graphs_empty_when_nothing_configured():
    assert mustrdStardog.dataset_graphs({}) == []


def test_query_with_bindings_injects_values():
    out = mustrdStardog.query_with_bindings(
        {Variable("x"): Literal("v")}, "SELECT * WHERE { ?x ?p ?o }")
    assert "VALUES ?x" in out
    assert out.strip().startswith("SELECT *")


class _FakeResponse:
    def __init__(self, status_code=200, content=b"ok"):
        self.status_code = status_code
        self.content = content


def test_select_posts_query_with_dataset_params():
    ts = {
        "url": "http://localhost",
        "port": "5820",
        "database": "mustrd",
        "token": "tok",
        "input_graph": "http://ex/input",
        "materialised_graphs": ["http://ex/mat"],
        "virtual_graphs": ["virtual://v"],
    }
    captured = {}

    def fake_post(url, data, params, auth, headers):
        captured["url"] = url
        captured["params"] = params
        captured["auth"] = auth
        captured["headers"] = headers
        return _FakeResponse(200, b"results")

    with patch.object(mustrdStardog.requests, "post", side_effect=fake_post):
        result = mustrdStardog.execute_select(ts, "SELECT * WHERE { ?s ?p ?o }")

    assert result == "results"
    assert captured["url"] == "http://localhost:5820/mustrd/query"
    assert captured["auth"] is None
    assert captured["headers"]["Authorization"] == "Bearer tok"
    # The whole combination is exposed as both default and named graphs
    assert captured["params"]["default-graph-uri"] == [
        "http://ex/input", "http://ex/mat", "virtual://v"]
    assert captured["params"]["named-graph-uri"] == [
        "http://ex/input", "http://ex/mat", "virtual://v"]


def test_upload_given_puts_turtle_to_input_graph():
    ts = {
        "url": "http://localhost:5820",
        "database": "mustrd",
        "username": "admin",
        "password": "admin",
        "input_graph": "http://ex/input",
    }
    captured = {}

    def fake_put(url, auth, data, headers):
        captured["url"] = url
        captured["auth"] = auth
        captured["headers"] = headers
        return _FakeResponse(204, b"")

    given = Graph()
    given.parse(data="<http://ex/s> <http://ex/p> <http://ex/o> .", format="ttl")

    with patch.object(mustrdStardog.requests, "put", side_effect=fake_put):
        mustrdStardog.upload_given(ts, given)

    assert captured["url"].startswith("http://localhost:5820/mustrd?graph=")
    assert "http%3A%2F%2Fex%2Finput" in captured["url"]
    assert captured["auth"] == ("admin", "admin")
    assert captured["headers"]["Content-Type"] == "text/turtle"


def test_auth_error_raises():
    ts = {"url": "http://localhost:5820", "database": "mustrd", "token": "bad"}
    with patch.object(mustrdStardog.requests, "post",
                      side_effect=lambda **kw: _FakeResponse(401, b"nope")):
        with pytest.raises(Exception):
            mustrdStardog.execute_select(ts, "SELECT * WHERE { ?s ?p ?o }")
