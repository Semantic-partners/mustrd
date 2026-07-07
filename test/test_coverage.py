"""Unit tests for ontology term coverage (mustrd/coverage.py)."""
from rdflib import Graph

from mustrd.coverage import (
    compute_coverage, declared_terms, query_uris, abox_terms,
    expand_ontology_files, load_ontology, ontology_report,
)

ONTO = """
@prefix geo:  <http://geo.org/> .
@prefix owl:  <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
geo:Place a owl:Class .
geo:City a owl:Class ; rdfs:subClassOf geo:Place .
geo:Country a owl:Class ; rdfs:subClassOf geo:Place .
geo:AdministrativeDivision a owl:Class ; rdfs:subClassOf geo:Place .
geo:isLocatedIn a owl:ObjectProperty, owl:TransitiveProperty ;
    rdfs:domain geo:Place ; rdfs:range geo:Place .
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

    assert by["geo:City"]["status"] == "covered" and by["geo:City"]["in_data"]      # data-only
    assert by["geo:Country"]["in_data"] and by["geo:Country"]["in_query"]           # fully exercised
    assert by["geo:isLocatedIn"]["status"] == "covered"
    # Place: domain/range of the used isLocatedIn + superclass of used classes -> schema, excluded
    assert by["geo:Place"]["status"] == "schema" and by["geo:Place"]["in_schema"]
    # AdministrativeDivision: not used and not structural -> a genuine gap
    assert by["geo:AdministrativeDivision"]["status"] == "unused"

    # covered = City, Country, isLocatedIn; denominator excludes schema-only Place
    assert cov["covered"] == 3 and cov["denominator"] == 4 and cov["pct"] == 75
    assert cov["declared_total"] == 5 and cov["schema_count"] == 1
    assert {g["term"] for g in cov["gaps"]} == {"geo:AdministrativeDivision"}
    place = next(s for s in cov["schema_terms"] if s["term"] == "geo:Place")
    assert "geo:isLocatedIn" in place["reason"]


def test_failing_spec_is_not_credited():
    cov = compute_coverage([_spec(passed=False, given=_graph(ONTO, DATA), queries=[QUERY])])
    assert cov["covered"] == 0
    assert cov["per_cq"][0]["credited"] is False


def test_tbox_only_given_yields_no_usage():
    # The ontology on its own declares terms but instantiates/queries nothing,
    # proving TBox declarations do not inflate coverage. With nothing used,
    # nothing is structural either, so all terms are genuine gaps.
    cov = compute_coverage([_spec(given=_graph(ONTO), queries=[])])
    assert cov["declared_total"] == 5 and cov["covered"] == 0 and cov["schema_count"] == 0


def test_no_declared_terms_returns_none():
    assert compute_coverage([_spec(given=_graph(DATA), queries=[QUERY])]) is None


def test_declared_terms_come_from_explicit_ontology():
    # The given holds only instance data (no TBox); declared terms must still be
    # found from the explicitly-passed ontology graph.
    cov = compute_coverage([_spec(given=_graph(DATA), queries=[QUERY])],
                           ontology=_graph(ONTO))
    assert cov is not None
    by = {t["term"]: t for t in cov["terms"]}
    assert by["geo:City"]["status"] == "covered"
    assert by["geo:Place"]["status"] == "schema"  # domain/range of used isLocatedIn


def test_expand_ontology_files_scans_directories_recursively(tmp_path):
    (tmp_path / "a.ttl").write_text(ONTO)
    nested = tmp_path / "sub" / "deep"
    nested.mkdir(parents=True)
    (nested / "b.ttl").write_text(DATA)
    (tmp_path / "notes.txt").write_text("ignore me")
    found = {f.name for f in expand_ontology_files([tmp_path])}
    assert found == {"a.ttl", "b.ttl"}  # recursive; non-RDF skipped


def test_ontology_report_extracts_uri_and_description(tmp_path):
    onto = tmp_path / "geo.ttl"
    onto.write_text(ONTO + """
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
<http://geo.org/> a <http://www.w3.org/2002/07/owl#Ontology> ;
    rdfs:comment "A tiny geography ontology." .
""")
    rows = ontology_report([onto], link_base=tmp_path)
    assert len(rows) == 1
    r = rows[0]
    assert r["path"].endswith("geo.ttl")
    # href is relative to link_base (renders in a markdown previewer)
    assert r["url"] == "geo.ttl"
    assert r["uri"] == "http://geo.org/"
    assert r["description"] == "A tiny geography ontology."


def test_ontology_report_file_without_ontology_header(tmp_path):
    onto = tmp_path / "vocab.ttl"
    onto.write_text(ONTO)  # declares classes but no owl:Ontology
    rows = ontology_report([onto])
    assert len(rows) == 1 and rows[0]["uri"] is None


def test_load_ontology_merges_files(tmp_path):
    (tmp_path / "onto.ttl").write_text(ONTO)
    g = load_ontology([tmp_path])
    assert g is not None
    assert set(declared_terms(g)) >= {"http://geo.org/Place", "http://geo.org/isLocatedIn"}


def test_load_ontology_empty_returns_none(tmp_path):
    assert load_ontology([tmp_path / "does-not-exist"]) is None
