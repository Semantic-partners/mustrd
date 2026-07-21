"""Unit tests for ontology term coverage (mustrd/coverage.py)."""
from rdflib import Graph

from mustrd.coverage import (
    compute_coverage, declared_terms, query_uris, abox_terms,
    expand_ontology_files, load_ontology, ontology_report,
)

# A neutral namespace/prefix for the fixtures. (Avoid `geo`, which rdflib
# pre-binds to GeoSPARQL and would rename an author's `geo:` to `geo1:`.)
ONTO = """
@prefix onto: <http://onto.org/> .
@prefix owl:  <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
onto:Place a owl:Class .
onto:City a owl:Class ; rdfs:subClassOf onto:Place .
onto:Country a owl:Class ; rdfs:subClassOf onto:Place .
onto:AdministrativeDivision a owl:Class ; rdfs:subClassOf onto:Place .
onto:isLocatedIn a owl:ObjectProperty, owl:TransitiveProperty ;
    rdfs:domain onto:Place ; rdfs:range onto:Place .
"""

DATA = """
@prefix onto: <http://onto.org/> .
@prefix ex:   <http://example.org/> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
ex:Rotterdam a onto:City ; rdfs:label "Rotterdam" ; onto:isLocatedIn ex:NL .
ex:NL a onto:Country ; rdfs:label "NL" .
"""

QUERY = """
PREFIX onto: <http://onto.org/>
# comment naming onto:Place must NOT count as usage
SELECT ?c WHERE { ?x onto:isLocatedIn ?c . ?c a onto:Country . }
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
        "http://onto.org/Place", "http://onto.org/City", "http://onto.org/Country",
        "http://onto.org/AdministrativeDivision", "http://onto.org/isLocatedIn",
    }
    assert d["http://onto.org/isLocatedIn"] == "property"
    assert d["http://onto.org/City"] == "class"


def test_query_uris_ignores_comments():
    uris = query_uris(QUERY)
    assert "http://onto.org/Country" in uris
    assert "http://onto.org/isLocatedIn" in uris
    assert "http://onto.org/Place" not in uris  # only mentioned in a comment


def test_abox_terms_are_types_and_predicates():
    used = abox_terms(_graph(DATA))
    assert "http://onto.org/City" in used        # rdf:type object
    assert "http://onto.org/Country" in used      # rdf:type object
    assert "http://onto.org/isLocatedIn" in used  # asserted predicate


def test_coverage_roles_and_percentage():
    cov = compute_coverage([_spec(given=_graph(ONTO, DATA), queries=[QUERY])])
    by = {t["term"]: t for t in cov["terms"]}

    assert by["onto:City"]["status"] == "covered" and by["onto:City"]["in_data"]      # data-only
    assert by["onto:Country"]["in_data"] and by["onto:Country"]["in_query"]           # fully exercised
    assert by["onto:isLocatedIn"]["status"] == "covered"
    # Place: domain/range of the used isLocatedIn + superclass of used classes -> schema, excluded
    assert by["onto:Place"]["status"] == "schema" and by["onto:Place"]["in_schema"]
    # AdministrativeDivision: not used and not structural -> a genuine gap
    assert by["onto:AdministrativeDivision"]["status"] == "unused"

    # covered = City, Country, isLocatedIn; denominator excludes schema-only Place
    assert cov["covered"] == 3 and cov["denominator"] == 4 and cov["pct"] == 75
    assert cov["declared_total"] == 5 and cov["schema_count"] == 1
    assert {g["term"] for g in cov["gaps"]} == {"onto:AdministrativeDivision"}
    place = next(s for s in cov["schema_terms"] if s["term"] == "onto:Place")
    assert "onto:isLocatedIn" in place["reason"]


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
    assert by["onto:City"]["status"] == "covered"
    assert by["onto:Place"]["status"] == "schema"  # domain/range of used isLocatedIn


ANNOTATION_ONTO = """
@prefix onto: <http://onto.org/> .
@prefix owl:  <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
onto:City a owl:Class .
onto:isLocatedIn a owl:ObjectProperty ; rdfs:domain onto:City .
onto:editorialNote a owl:AnnotationProperty .
onto:versionInfo a owl:OntologyProperty .
"""


def test_annotation_and_ontology_properties_are_schema_not_gaps():
    # An unused annotation/ontology property is metadata, not a coverage gap:
    # it lands in the schema bucket and is excluded from the denominator.
    data = """
    @prefix onto: <http://onto.org/> .
    @prefix ex:   <http://example.org/> .
    ex:Rotterdam a onto:City ; onto:isLocatedIn ex:NL .
    """
    cov = compute_coverage([_spec(given=_graph(data), queries=[])],
                           ontology=_graph(ANNOTATION_ONTO))
    by = {t["term"]: t for t in cov["terms"]}

    assert by["onto:editorialNote"]["status"] == "schema"
    assert by["onto:versionInfo"]["status"] == "schema"
    # neither is reported as a gap
    gap_terms = {g["term"] for g in cov["gaps"]}
    assert "onto:editorialNote" not in gap_terms and "onto:versionInfo" not in gap_terms
    # and both are excluded from the coverage denominator
    assert by["onto:City"]["status"] == "covered"
    assert cov["schema_count"] == 2 and cov["denominator"] == 2
    reasons = {s["term"]: s["reason"] for s in cov["schema_terms"]}
    assert reasons["onto:editorialNote"] == "annotation property"
    assert reasons["onto:versionInfo"] == "ontology property"


def test_used_annotation_property_still_counts_as_covered():
    # If a CQ actually exercises an annotation property, it is covered, not schema.
    data = """
    @prefix onto: <http://onto.org/> .
    @prefix ex:   <http://example.org/> .
    ex:Rotterdam a onto:City ; onto:editorialNote "note" .
    """
    cov = compute_coverage([_spec(given=_graph(data), queries=[])],
                           ontology=_graph(ANNOTATION_ONTO))
    by = {t["term"]: t for t in cov["terms"]}
    assert by["onto:editorialNote"]["status"] == "covered"


def test_requires_ontology_when_query_needs_class_hierarchy():
    # Query asks for a superclass (onto:Place) that no data instance is typed as;
    # only subclass instances (onto:City) exist, so the rdfs:subClassOf axiom must
    # be loaded for the query to match -> "requires ontology to pass".
    data = _graph("""
    @prefix onto: <http://onto.org/> .
    @prefix ex:   <http://example.org/> .
    ex:Rotterdam a onto:City .
    """)
    query = """PREFIX onto: <http://onto.org/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?x WHERE { ?x a/rdfs:subClassOf* onto:Place }"""
    cov = compute_coverage([_spec(given=data, queries=[query])], ontology=_graph(ONTO))
    assert cov["per_cq"][0]["requires_ontology"] is True


def test_not_requires_ontology_when_data_has_queried_type():
    # Query asks for onto:Country and data has Country instances directly, so it
    # passes without the class hierarchy -> not flagged.
    data = _graph("""
    @prefix onto: <http://onto.org/> .
    @prefix ex:   <http://example.org/> .
    ex:NL a onto:Country .
    """)
    query = """PREFIX onto: <http://onto.org/>
    SELECT ?x WHERE { ?x a onto:Country }"""
    cov = compute_coverage([_spec(given=data, queries=[query])], ontology=_graph(ONTO))
    assert cov["per_cq"][0]["requires_ontology"] is False


def test_expand_ontology_files_scans_directories_recursively(tmp_path):
    (tmp_path / "a.ttl").write_text(ONTO)
    nested = tmp_path / "sub" / "deep"
    nested.mkdir(parents=True)
    (nested / "b.ttl").write_text(DATA)
    (tmp_path / "notes.txt").write_text("ignore me")
    found = {f.name for f in expand_ontology_files([tmp_path])}
    assert found == {"a.ttl", "b.ttl"}  # recursive; non-RDF skipped


def test_ontology_report_extracts_uri_and_description(tmp_path):
    onto = tmp_path / "onto.ttl"
    onto.write_text(ONTO + """
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
<http://onto.org/> a <http://www.w3.org/2002/07/owl#Ontology> ;
    rdfs:comment "A tiny example ontology." .
""")
    rows = ontology_report([onto], link_base=tmp_path)
    assert len(rows) == 1
    r = rows[0]
    assert r["path"].endswith("onto.ttl")
    # href is relative to link_base (renders in a markdown previewer)
    assert r["url"] == "onto.ttl"
    assert r["uri"] == "http://onto.org/"
    assert r["description"] == "A tiny example ontology."


def test_ontology_report_file_without_ontology_header(tmp_path):
    onto = tmp_path / "vocab.ttl"
    onto.write_text(ONTO)  # declares classes but no owl:Ontology
    rows = ontology_report([onto])
    assert len(rows) == 1 and rows[0]["uri"] is None


def test_load_ontology_merges_files(tmp_path):
    (tmp_path / "onto.ttl").write_text(ONTO)
    g = load_ontology([tmp_path])
    assert g is not None
    assert set(declared_terms(g)) >= {"http://onto.org/Place", "http://onto.org/isLocatedIn"}


def test_load_ontology_empty_returns_none(tmp_path):
    assert load_ontology([tmp_path / "does-not-exist"]) is None
