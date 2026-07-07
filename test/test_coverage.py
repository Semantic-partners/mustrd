"""Unit tests for ontology term coverage (mustrd/coverage.py)."""
from rdflib import Graph

from mustrd.coverage import compute_coverage, declared_terms, query_uris, abox_terms

ONTO = """
@prefix geo:  <http://geo.org/> .
@prefix owl:  <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
geo:Place a owl:Class .
geo:City a owl:Class ; rdfs:subClassOf geo:Place .
geo:Country a owl:Class ; rdfs:subClassOf geo:Place .
geo:AdministrativeDivision a owl:Class ; rdfs:subClassOf geo:Place .
geo:isLocatedIn a owl:ObjectProperty, owl:TransitiveProperty .
"""

DATA = """
@prefix geo:  <http://geo.org/> .
@prefix ex:   <http://example.org/> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
ex:Rotterdam a geo:City ; rdfs:label "Rotterdam" ; geo:isLocatedIn ex:NL .
ex:NL a geo:Country ; rdfs:label "NL" .
"""

QUERY = """
PREFIX geo: <http://geo.org/>
# comment naming geo:Place must NOT count as usage
SELECT ?c WHERE { ?x geo:isLocatedIn ?c . ?c a geo:Country . }
"""


def _graph(*ttls):
    g = Graph()
    for t in ttls:
        g.parse(data=t, format="turtle")
    return g


def _spec(passed=True, given=None, queries=(), name="a.mustrd.ttl", cq="Q?"):
    return {"name": name, "cq": cq, "passed": passed,
            "given": given, "queries": list(queries)}


def test_declared_terms_excludes_well_known_vocab():
    d = declared_terms(_graph(ONTO))
    assert set(d) == {
        "http://geo.org/Place", "http://geo.org/City", "http://geo.org/Country",
        "http://geo.org/AdministrativeDivision", "http://geo.org/isLocatedIn",
    }
    assert d["http://geo.org/isLocatedIn"] == "property"
    assert d["http://geo.org/City"] == "class"


def test_query_uris_ignores_comments():
    uris = query_uris(QUERY)
    assert "http://geo.org/Country" in uris
    assert "http://geo.org/isLocatedIn" in uris
    assert "http://geo.org/Place" not in uris  # only mentioned in a comment


def test_abox_terms_are_types_and_predicates():
    used = abox_terms(_graph(DATA))
    assert "http://geo.org/City" in used        # rdf:type object
    assert "http://geo.org/Country" in used      # rdf:type object
    assert "http://geo.org/isLocatedIn" in used  # asserted predicate


def test_coverage_roles_and_percentage():
    cov = compute_coverage([_spec(given=_graph(ONTO, DATA), queries=[QUERY])])
    by = {t["term"]: t for t in cov["terms"]}

    assert by["geo:City"]["in_data"] and not by["geo:City"]["in_query"]        # data-only
    assert by["geo:Country"]["in_data"] and by["geo:Country"]["in_query"]      # fully exercised
    assert by["geo:isLocatedIn"]["used"]
    assert not by["geo:Place"]["used"]                                         # unused
    assert not by["geo:AdministrativeDivision"]["used"]                        # unused

    assert cov["covered"] == 3 and cov["declared"] == 5 and cov["pct"] == 60
    assert {u["term"] for u in cov["unused"]} == {"geo:Place", "geo:AdministrativeDivision"}


def test_failing_spec_is_not_credited():
    cov = compute_coverage([_spec(passed=False, given=_graph(ONTO, DATA), queries=[QUERY])])
    assert cov["covered"] == 0
    assert cov["per_cq"][0]["credited"] is False


def test_tbox_only_given_yields_no_usage():
    # The ontology on its own declares terms but instantiates/queries nothing,
    # proving TBox declarations do not inflate coverage.
    cov = compute_coverage([_spec(given=_graph(ONTO), queries=[])])
    assert cov["declared"] == 5 and cov["covered"] == 0


def test_no_declared_terms_returns_none():
    assert compute_coverage([_spec(given=_graph(DATA), queries=[QUERY])]) is None
