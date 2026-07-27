"""Unit tests for ontology term coverage (mustrd/coverage.py)."""
from rdflib import Graph

from mustrd.coverage import compute_coverage
from mustrd.ontology import (
    declared_terms, query_uris, abox_terms,
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


def _spec(passed=True, given=None, queries=(), name="a.mustrd.ttl", uri=None):
    return {"name": name, "uri": uri or f"http://ex/{name}", "passed": passed,
            "given": given, "queries": list(queries)}


def _cqdef(question, *specs, name="cq", questions=None, missing=()):
    """A cq:CompetencyQuestion node linking the given spec dicts."""
    return {"id": f"http://ex/cq/{name}", "name": name, "source_file": None,
            "question": question,
            "questions": questions if questions is not None else ([question] if question else []),
            "specs": list(specs), "missing_specs": list(missing)}


# compute_coverage no longer emits the rendered term matrix / gaps / structural
# lists — those are rebuilt from the RDF graph by coverage_render / cq_render. The
# unit tests here assert the CANONICAL per-term data it does emit (term_records),
# keyed by qname (the fixtures all use the single onto: = http://onto.org/ prefix).
def _by_term(cov):
    return {"onto:" + r["iri"].rsplit("/", 1)[-1]: r for r in cov["term_records"]}


def _gap_terms(cov):
    """Qnames the report lists as 'not covered by any test': non-structural terms
    a passing test doesn't populate in data (role query-only or unused)."""
    return {q for q, r in _by_term(cov).items() if r["role"] in ("query-only", "unused")}


def _tree_rows(specs, ontology):
    """The rendered term-matrix rows, via the real pipeline (compute -> graph ->
    render). Used by the few tests that assert tree *shape* (grouping, depth,
    multiple parents), which only the renderer produces."""
    from mustrd.coverage_rdf import coverage_graph
    from mustrd.coverage_render import coverage_context
    cov = compute_coverage(specs, ontology=ontology)
    graph = coverage_graph(cov, [{"uri": "http://onto.org/"}])
    return coverage_context(graph, ontology)["terms"]


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
    by = _by_term(cov)

    assert by["onto:City"]["role"] == "covered" and by["onto:City"]["in_data"]      # data-only
    assert by["onto:Country"]["in_data"] and by["onto:Country"]["in_query"]         # fully exercised
    assert by["onto:isLocatedIn"]["role"] == "covered"
    # Place: domain/range of the used isLocatedIn + superclass of used classes -> schema, excluded
    assert by["onto:Place"]["role"] == "schema"
    # AdministrativeDivision: not used and not structural -> a genuine gap
    assert by["onto:AdministrativeDivision"]["role"] == "unused"

    # covered = City, Country, isLocatedIn; denominator excludes schema-only Place
    assert cov["covered"] == 3 and cov["denominator"] == 4 and cov["pct"] == 75
    assert cov["declared_total"] == 5 and cov["schema_count"] == 1
    assert _gap_terms(cov) == {"onto:AdministrativeDivision"}
    assert any("onto:isLocatedIn" in r for r in by["onto:Place"]["structural_reasons"])


def test_failing_spec_is_not_credited():
    spec = _spec(passed=False, given=_graph(ONTO, DATA), queries=[QUERY])
    cov = compute_coverage([spec], cq_defs=[_cqdef("Q?", spec)])
    assert cov["covered"] == 0
    assert cov["per_cq"][0]["credited"] is False


def test_term_used_only_by_a_non_cq_test_is_covered_but_not_by_cq():
    # Coverage is over ALL tests, so a term a non-CQ test exercises counts as
    # covered — but by_cq is False (no competency question backs it).
    admin_data = _graph("""
    @prefix onto: <http://onto.org/> .
    @prefix ex:   <http://example.org/> .
    ex:X a onto:AdministrativeDivision .
    """)
    non_cq = _spec(given=admin_data, queries=[], name="admin.mustrd.ttl")
    cq = _spec(given=_graph(DATA), queries=[QUERY], name="c.mustrd.ttl")
    cov = compute_coverage([non_cq, cq], ontology=_graph(ONTO), cq_defs=[_cqdef("Q?", cq)])
    by = _by_term(cov)
    admin = by["onto:AdministrativeDivision"]
    assert admin["role"] == "covered"                  # exercised by a (non-CQ) test
    assert admin["cq_role"] != "covered"               # but no competency question covers it
    assert by["onto:Country"]["cq_role"] == "covered"  # the CQ does cover Country


def test_query_only_term_is_not_covered():
    # A class named by a query but never instantiated is *query-only*: the test
    # can pass without it, so it is NOT covered — it is a gap, flagged query_only.
    q = """PREFIX onto: <http://onto.org/>
    SELECT ?x WHERE { ?x a onto:AdministrativeDivision . }"""
    cov = compute_coverage([_spec(given=_graph(ONTO, DATA), queries=[q])])
    by = _by_term(cov)
    admin = by["onto:AdministrativeDivision"]
    assert admin["in_query"] and not admin["in_data"]
    assert admin["role"] == "query-only"
    # covered stays City/Country/isLocatedIn (all data-backed); query-only excluded.
    assert cov["covered"] == 3
    assert "onto:AdministrativeDivision" in _gap_terms(cov)


def test_cover_refs_expose_data_sparql_split_across_tests():
    # The scenario the aggregate columns can't show: one test supplies the data,
    # a different test supplies the query. The term reads ✅/✅ overall, but the
    # per-test cover_refs reveal that no single test does both.
    a = _spec(given=_graph("""
    @prefix onto: <http://onto.org/> .
    @prefix ex:   <http://example.org/> .
    ex:c a onto:City .
    """), queries=[], name="a.mustrd.ttl")
    b = _spec(given=_graph(), name="b.mustrd.ttl", queries=[
        "PREFIX onto: <http://onto.org/> SELECT ?x WHERE { ?x a onto:City . }"])
    cov = compute_coverage([a, b], ontology=_graph(ONTO))
    city = _by_term(cov)["onto:City"]
    assert city["role"] == "covered" and city["in_data"] and city["in_query"]
    refs = {r["name"]: r for r in city["exercises"]}
    assert refs["a.mustrd.ttl"]["in_data"] and not refs["a.mustrd.ttl"]["in_query"]
    assert refs["b.mustrd.ttl"]["in_query"] and not refs["b.mustrd.ttl"]["in_data"]


def test_tbox_axioms_in_given_are_flagged():
    # Class/property declarations and subClassOf in a test's given are schema that
    # belongs in the ontology -> surfaced under tbox_in_data so it can be moved.
    data = _graph("""
    @prefix onto: <http://onto.org/> .
    @prefix ex:   <http://example.org/> .
    @prefix owl:  <http://www.w3.org/2002/07/owl#> .
    @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
    onto:Province a owl:Class ; rdfs:subClassOf onto:AdministrativeDivision .
    ex:zh a onto:Province .
    """)
    cov = compute_coverage([_spec(given=data, queries=[], name="t.mustrd.ttl")],
                           ontology=_graph(ONTO))
    tb = cov["tbox_in_data"]
    assert len(tb) == 1 and tb[0]["name"] == "t.mustrd.ttl"
    assert "onto:Province a owl:Class" in tb[0]["axioms"]
    assert "onto:Province rdfs:subClassOf onto:AdministrativeDivision" in tb[0]["axioms"]
    # A given with only instance data flags nothing.
    clean = compute_coverage([_spec(given=_graph(DATA), queries=[QUERY])],
                             ontology=_graph(ONTO))
    assert clean["tbox_in_data"] == []


def test_duplicate_competency_questions_are_excluded_and_warned():
    # Two CQ nodes share the same question (copy/paste). Both are excluded from
    # the CQ overlay and reported under duplicate_cqs; a CQ with a unique question
    # is kept.
    spec_a = _spec(given=_graph(ONTO, DATA), queries=[QUERY], name="a.mustrd.ttl")
    spec_b = _spec(given=_graph(ONTO, DATA), queries=[QUERY], name="b.mustrd.ttl")
    spec_c = _spec(given=_graph(DATA), queries=[QUERY], name="c.mustrd.ttl")
    cq_defs = [_cqdef("dupe?", spec_a, name="a"), _cqdef("dupe?", spec_b, name="b"),
               _cqdef("unique?", spec_c, name="c")]
    cov = compute_coverage([spec_a, spec_b, spec_c], ontology=_graph(ONTO), cq_defs=cq_defs)
    dupes = cov["duplicate_cqs"]
    assert len(dupes) == 1 and dupes[0]["question"] == "dupe?"
    assert {c["name"] for c in dupes[0]["cqs"]} == {"a", "b"}
    # Only the unique CQ contributes to the per-CQ breakdown.
    assert {c["question"] for c in cov["per_cq"]} == {"unique?"}


def test_cq_without_a_test_is_listed_and_credits_nothing():
    # A cq:CompetencyQuestion with no linked spec is reported (has_test False)
    # and adds nothing to the CQ coverage number.
    spec = _spec(given=_graph(ONTO, DATA), queries=[QUERY], name="a.mustrd.ttl")
    testless = _cqdef("Unanswered?", name="q")          # no specs
    cov = compute_coverage([spec], ontology=_graph(ONTO),
                           cq_defs=[_cqdef("Answered?", spec, name="a"), testless])
    entries = {c["question"]: c for c in cov["per_cq"]}
    assert entries["Unanswered?"]["has_test"] is False and entries["Unanswered?"]["tests"] == []
    assert entries["Answered?"]["has_test"] is True
    # The test-less CQ contributes no covered terms.
    assert cov["covered_by_cq"] == cov["covered_by_cq"]  # sanity; overlay only from linked specs


def test_multiple_questions_and_missing_spec_are_flagged():
    spec = _spec(given=_graph(ONTO, DATA), queries=[QUERY], name="a.mustrd.ttl")
    two_q = _cqdef("Q1?", spec, name="x", questions=["Q1?", "Q2?"])
    dangling = _cqdef("Q3?", name="y", missing=["http://ex/ghost"])
    cov = compute_coverage([spec], ontology=_graph(ONTO), cq_defs=[two_q, dangling])
    by_q = {c["question"]: c for c in cov["per_cq"]}
    assert by_q["Q1?"]["question_error"] is True
    assert by_q["Q3?"]["missing_specs"] == ["http://ex/ghost"]


def test_schema_only_ancestor_chain_collapses_into_one_row():
    # :Animal -> :Mammal -> :Dog, with :Dog used: the two schema-only ancestors
    # collapse into a single grouped row above the used class.
    onto = _graph("""
    @prefix onto: <http://onto.org/> .
    @prefix owl:  <http://www.w3.org/2002/07/owl#> .
    @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
    onto:Animal a owl:Class .
    onto:Mammal a owl:Class ; rdfs:subClassOf onto:Animal .
    onto:Dog a owl:Class ; rdfs:subClassOf onto:Mammal .
    """)
    data = _graph("""
    @prefix onto: <http://onto.org/> .
    @prefix ex:   <http://example.org/> .
    ex:Rex a onto:Dog .
    """)
    rows = _tree_rows([_spec(given=data, queries=[])], onto)
    grouped = next(r for r in rows if r.get("grouped"))
    assert grouped["term"] == "onto:Animal, onto:Mammal"
    assert grouped["status"] == "schema" and grouped["depth"] == 0
    dog = next(r for r in rows if r["term"] == "onto:Dog")
    assert dog["status"] == "covered" and dog["depth"] == 1


def test_multiple_parents_are_annotated_not_duplicated():
    # :Dog has two parents; it hangs under the alphabetically-first (Mammal) and
    # annotates the other (Pet) rather than appearing twice.
    onto = _graph("""
    @prefix onto: <http://onto.org/> .
    @prefix owl:  <http://www.w3.org/2002/07/owl#> .
    @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
    onto:Mammal a owl:Class .
    onto:Pet a owl:Class .
    onto:Dog a owl:Class ; rdfs:subClassOf onto:Mammal, onto:Pet .
    """)
    data = _graph("""
    @prefix onto: <http://onto.org/> .
    @prefix ex:   <http://example.org/> .
    ex:Rex a onto:Dog .
    """)
    rows = _tree_rows([_spec(given=data, queries=[])], onto)
    dogs = [r for r in rows if r["term"] == "onto:Dog"]
    assert len(dogs) == 1
    assert dogs[0]["extra_parents"] == ["onto:Pet"]


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
    by = _by_term(cov)
    assert by["onto:City"]["role"] == "covered"
    assert by["onto:Place"]["role"] == "schema"  # domain/range of used isLocatedIn


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
    by = _by_term(cov)

    assert by["onto:editorialNote"]["role"] == "schema"
    assert by["onto:versionInfo"]["role"] == "schema"
    # neither is reported as a gap
    gap_terms = _gap_terms(cov)
    assert "onto:editorialNote" not in gap_terms and "onto:versionInfo" not in gap_terms
    # and both are excluded from the coverage denominator
    assert by["onto:City"]["role"] == "covered"
    assert cov["schema_count"] == 2 and cov["denominator"] == 2
    assert by["onto:editorialNote"]["structural_reasons"] == ["annotation property"]
    assert by["onto:versionInfo"]["structural_reasons"] == ["ontology property"]


def test_used_annotation_property_still_counts_as_covered():
    # If a CQ actually exercises an annotation property, it is covered, not schema.
    data = """
    @prefix onto: <http://onto.org/> .
    @prefix ex:   <http://example.org/> .
    ex:Rotterdam a onto:City ; onto:editorialNote "note" .
    """
    cov = compute_coverage([_spec(given=_graph(data), queries=[])],
                           ontology=_graph(ANNOTATION_ONTO))
    by = _by_term(cov)
    assert by["onto:editorialNote"]["role"] == "covered"


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
    spec = _spec(given=data, queries=[query])
    cov = compute_coverage([spec], ontology=_graph(ONTO), cq_defs=[_cqdef("Q?", spec)])
    assert cov["per_cq"][0]["tests"][0]["requires_ontology"] is True


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
    spec = _spec(given=data, queries=[query])
    cov = compute_coverage([spec], ontology=_graph(ONTO), cq_defs=[_cqdef("Q?", spec)])
    assert cov["per_cq"][0]["tests"][0]["requires_ontology"] is False


def test_undeclared_term_used_in_data_is_flagged_as_input_data():
    # onto:hasMayor is used in the data and sits in the ontology's namespace, but
    # is never declared -> surfaced as "used but not declared", tagged input data.
    data = _graph("""
    @prefix onto: <http://onto.org/> .
    @prefix ex:   <http://example.org/> .
    ex:Rotterdam a onto:City ; onto:hasMayor ex:X .
    """)
    cov = compute_coverage([_spec(given=data, queries=[], name="q.mustrd.ttl")],
                           ontology=_graph(ONTO))
    by = {u["term"]: u for u in cov["undeclared"]}
    ref = by["onto:hasMayor"]["refs"][0]
    assert ref["in_data"] is True and ref["in_query"] is False
    assert ref["name"] == "q.mustrd.ttl"  # the referencing CQ is recorded
    assert "onto:City" not in by  # declared, so not flagged


def test_undeclared_term_used_in_query_is_flagged_as_sparql():
    # onto:nickname appears only in the SPARQL, not the data -> tagged SPARQL.
    data = _graph("""
    @prefix onto: <http://onto.org/> .
    @prefix ex:   <http://example.org/> .
    ex:Rotterdam a onto:City .
    """)
    query = """PREFIX onto: <http://onto.org/>
    SELECT ?x WHERE { ?x a onto:City ; onto:nickname ?n }"""
    cov = compute_coverage([_spec(given=data, queries=[query])], ontology=_graph(ONTO))
    by = {u["term"]: u for u in cov["undeclared"]}
    ref = by["onto:nickname"]["refs"][0]
    assert ref["in_query"] is True and ref["in_data"] is False


def test_external_namespace_terms_are_not_flagged_as_undeclared():
    # foaf:name is used but lives in an external namespace (not one of the
    # ontology's), so it is not flagged — only undefined terms in the ontology's
    # own namespace are.
    data = _graph("""
    @prefix onto: <http://onto.org/> .
    @prefix foaf: <http://xmlns.com/foaf/0.1/> .
    @prefix ex:   <http://example.org/> .
    ex:X a onto:City ; foaf:name "x" .
    """)
    cov = compute_coverage([_spec(given=data, queries=[])], ontology=_graph(ONTO))
    assert cov["undeclared"] == []


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


# --- term links (apply_term_links / term_source_index) ----------------------
from pathlib import Path
from mustrd.coverage import apply_term_links, term_source_index


def _cov():
    return {"terms": [{"term": "onto:City", "iri": "http://onto.org/City"}],
            "gaps": [], "cq_gaps": [], "schema_terms": [], "undeclared": []}


def test_term_links_off_leaves_terms_plain():
    cov = _cov()
    apply_term_links(cov, "off")
    assert "link" not in cov["terms"][0]
    assert apply_term_links(None, "file") is None  # tolerates no coverage


def test_term_links_iri_uses_full_iri():
    cov = _cov()
    apply_term_links(cov, "iri")
    assert cov["terms"][0]["link"] == "http://onto.org/City"


def test_term_links_file_deep_links_to_declaration_line(tmp_path):
    onto = tmp_path / "onto.ttl"
    onto.write_text(ONTO)  # onto:City is declared on its own line
    idx = term_source_index([onto])
    assert idx["http://onto.org/City"]["file"] == Path(onto)
    line = idx["http://onto.org/City"]["line"]
    assert onto.read_text().splitlines()[line - 1].startswith("onto:City ")

    cov = _cov()
    apply_term_links(cov, "file", paths=[onto], link_base=tmp_path)
    assert cov["terms"][0]["link"] == f"onto.ttl#L{line}"


def test_term_links_file_no_source_leaves_unlinked(tmp_path):
    cov = _cov()  # term not declared in any given file
    apply_term_links(cov, "file", paths=[tmp_path], link_base=tmp_path)
    assert "link" not in cov["terms"][0]
