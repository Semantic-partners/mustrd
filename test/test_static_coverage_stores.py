"""Static coverage contacts no store and reads no credentials.

`mustrd coverage`, `collect_specs` and `static_coverage` build every spec and run
none. They used to resolve each suite's triple stores anyway: with the store
config missing, or present without a token, `filterOnTripleStore` then removed
the rdflib fallback, the suite had no stores, and every spec was dropped without
a word. These tests pin the store-free path and the count of what was left out.
"""
import socket

import pytest

import mustrd.runner
from mustrd.cli import main
from mustrd.mustrdTestPlugin import MustrdTestPlugin
from mustrd.runner import collect_specs, collect_static, run_config, static_coverage

ONTO = """
@prefix onto: <http://onto.org/> .
@prefix owl:  <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
onto:Place a owl:Class .
onto:City a owl:Class ; rdfs:subClassOf onto:Place .
onto:Country a owl:Class ; rdfs:subClassOf onto:Place .
onto:isLocatedIn a owl:ObjectProperty ;
    rdfs:domain onto:Place ; rdfs:range onto:Place .
"""

SPEC = """
@prefix must: <https://mustrd.org/model/> .
@prefix ex:   <http://ex/> .
ex:inheritedCities
    a          must:TestSpec ;
    must:given [ a must:InheritedDataset ] ;
    must:when  [ a must:TextSparqlSource ;
                 must:queryText "PREFIX onto: <http://onto.org/> SELECT ?x WHERE { ?x a onto:City ; onto:isLocatedIn ?y }" ;
                 must:queryType must:SelectSparql ] ;
    must:then  [ a must:EmptyTable ] .
"""

# No `when`: fails the spec shapes, so it is left out — and must be reported.
INVALID_SPEC = """
@prefix must: <https://mustrd.org/model/> .
@prefix ex:   <http://ex/> .
ex:noWhen a must:TestSpec ;
    must:given [ a must:InheritedDataset ] ;
    must:then  [ a must:EmptyTable ] .
"""

CONFIG = """
@prefix :            <https://mustrd.org/mustrdTest/> .
@prefix triplestore: <https://mustrd.org/triplestore/> .
:stardogOnly a :MustrdTest ;
    :hasSpecPath          "specs" ;
    :hasDataPath          "data" ;
    :hasOntologyPath      "onto.ttl" ;
    :hasPytestPath        "stardog" ;
    :triplestoreSpecPath  "triplestore-config.ttl" ;
    :filterOnTripleStore  triplestore:SomeStardog .
"""

# A store config with no token, no pointer and no _secrets file beside it.
STORE_NO_TOKEN = """
@prefix : <https://mustrd.org/triplestore/> .
:SomeStardog a :Stardog ;
    :url "http://localhost" ; :port "5820" ; :database "db" ;
    :tokenEnv "MUSTRD_STATIC_TEST_UNSET" .
"""


@pytest.fixture
def no_network(monkeypatch):
    def refuse(*_a, **_k):
        pytest.fail("static coverage must not open a connection")
    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.delenv("MUSTRD_STATIC_TEST_UNSET", raising=False)


@pytest.fixture
def no_store_resolution(monkeypatch):
    def refuse(*_a, **_k):
        pytest.fail("static coverage must not resolve triple stores")
    monkeypatch.setattr(mustrd.runner, "resolve_triple_stores", refuse)


def _suite(root, store_config=None, invalid=False):
    (root / "specs").mkdir()
    (root / "data").mkdir()
    (root / "specs" / "inherited.mustrd.ttl").write_text(SPEC, encoding="utf-8")
    if invalid:
        (root / "specs" / "no-when.mustrd.ttl").write_text(INVALID_SPEC, encoding="utf-8")
    (root / "onto.ttl").write_text(ONTO, encoding="utf-8")
    (root / "mustrd-config.ttl").write_text(CONFIG, encoding="utf-8")
    if store_config is not None:
        (root / "triplestore-config.ttl").write_text(store_config, encoding="utf-8")
    return root / "mustrd-config.ttl"


@pytest.mark.parametrize("store_config", [None, STORE_NO_TOKEN],
                         ids=["no-store-config", "store-config-without-token"])
def test_stardog_only_suite_is_counted_without_store_or_token(
        tmp_path, store_config, no_network, no_store_resolution):
    config = _suite(tmp_path, store_config)

    cov = static_coverage(config)
    assert (cov["queried"], cov["denominator"]) == (2, 3)

    specs, by_uri, _ = collect_specs(config, secrets="ignored")
    assert [s["test_name"] for s in specs] == ["inherited.mustrd.ttl@SomeStardog"]
    assert "http://ex/inheritedCities" in by_uri


def test_one_placeholder_store_per_filter_value(tmp_path, no_network):
    config = _suite(tmp_path)
    config.write_text(CONFIG.replace(
        "triplestore:SomeStardog .",
        "triplestore:SomeStardog, triplestore:OtherStardog ."), encoding="utf-8")
    names = sorted(s["test_name"] for s in collect_static(config).all_specs)
    assert names == ["inherited.mustrd.ttl@OtherStardog", "inherited.mustrd.ttl@SomeStardog"]


def test_specs_left_out_are_counted_and_named(tmp_path, no_network):
    found = collect_static(_suite(tmp_path, invalid=True))
    assert found.summary() == "1 spec measured, 1 not counted"
    assert [lo["name"] for lo in found.left_out] == ["no-when.mustrd.ttl"]
    assert found.left_out[0]["reason"]


def test_cli_reports_measured_and_not_counted(tmp_path, capsys, monkeypatch, no_network,
                                              no_store_resolution):
    config = _suite(tmp_path, invalid=True)
    md = tmp_path / "out.md"
    assert main(["coverage", "--config", str(config), "--md", str(md)]) == 0
    out = capsys.readouterr().out
    assert "1 spec measured, 1 not counted" in out
    assert "not counted: no-when.mustrd.ttl:" in out
    assert "**Queried: 2/3 terms named by a query = 67%**" in md.read_text(encoding="utf-8")


def test_plugin_coverage_only_runs_nothing_and_reads_no_store(
        tmp_path, monkeypatch, no_network, no_store_resolution):
    config = _suite(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mustrd.runner, "run_spec",
                        lambda spec: pytest.fail("coverage-only must not run a spec"))
    md = tmp_path / "out.md"
    plugin = MustrdTestPlugin(str(md), config, None, term_coverage=True,
                              coverage_only=True)
    assert pytest.main([".", "-p", "no:cacheprovider", "-q"], plugins=[plugin]) == 0
    assert "**Queried: 2/3 terms named by a query = 67%**" in md.read_text(encoding="utf-8")


def test_run_config_still_resolves_the_configured_stores(monkeypatch):
    seen = []
    real = mustrd.runner.resolve_triple_stores

    def spy(test_config, secrets=None):
        seen.append(test_config)
        return real(test_config, secrets)
    monkeypatch.setattr(mustrd.runner, "resolve_triple_stores", spy)
    run_config("docs/examples/geography-example/mustrd-config.ttl")
    assert seen
