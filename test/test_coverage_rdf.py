"""Data-level tests: compute_coverage -> coverage_graph emits the right triples.

The RDF graph is the canonical output of a coverage run; here we assert the
*data* it contains, independently of how it's later rendered.
"""
from rdflib import Graph, URIRef, Namespace, RDF, XSD, Literal

from mustrd.coverage import compute_coverage
from mustrd.coverage_rdf import coverage_graph

COV = Namespace("https://mustrd.org/coverage/")
DQV = Namespace("http://www.w3.org/ns/dqv#")
PROV = Namespace("http://www.w3.org/ns/prov#")

ONTO = """
@prefix onto: <http://onto.org/> .
@prefix owl:  <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
onto:Place a owl:Class .
onto:City a owl:Class ; rdfs:subClassOf onto:Place .
onto:Country a owl:Class ; rdfs:subClassOf onto:Place .
onto:isLocatedIn a owl:ObjectProperty ; rdfs:domain onto:Place ; rdfs:range onto:Place .
"""
DATA = """
@prefix onto: <http://onto.org/> .
@prefix ex:   <http://example.org/> .
ex:Rotterdam a onto:City ; onto:isLocatedIn ex:NL .
ex:NL a onto:Country .
"""
QUERY = "PREFIX onto: <http://onto.org/> SELECT ?c WHERE { ?x onto:isLocatedIn ?c . ?c a onto:Country . }"


def _graph(*ttls):
    g = Graph()
    for t in ttls:
        g.parse(data=t, format="turtle")
    return g


def _build():
    spec = {"name": "a.mustrd.ttl", "uri": "http://ex/a", "passed": True,
            "given": _graph(ONTO, DATA), "queries": [QUERY]}
    cov = compute_coverage([spec], ontology=_graph(ONTO))
    g = coverage_graph(cov, [{"uri": "http://onto.org/", "version": "http://onto.org/1.0"}],
                       run_slug="test")
    return cov, g


def test_aggregate_measurement_is_a_ratio_computed_on_the_ontology():
    cov, g = _build()
    m = g.value(predicate=DQV.isMeasurementOf, object=COV.termCoverageByTests)
    assert m is not None
    val = g.value(m, DQV.value)
    assert val.datatype == XSD.decimal
    assert float(val) == round(cov["ratio"], 4)
    assert (m, DQV.computedOn, URIRef("http://onto.org/")) in g
    assert (m, DQV.computedOn, URIRef("http://onto.org/1.0")) in g  # versionIRI


def test_per_term_record_has_role_kind_and_per_test_exercise():
    _, g = _build()
    city = URIRef("https://mustrd.org/coverage/run/test/term/onto.City")
    assert (city, RDF.type, COV.TermCoverage) in g
    assert (city, COV["term"], URIRef("http://onto.org/City")) in g
    assert (city, COV.role, COV.Covered) in g
    assert (city, COV.kind, Literal("class")) in g
    # an Exercise sub-record links the test and records where it contributes
    ex = g.value(city, COV.exercise)
    assert ex is not None
    assert (ex, COV.test, URIRef("http://ex/a")) in g
    assert (ex, COV.inData, Literal(True)) in g


def test_structural_term_carries_a_reason():
    _, g = _build()
    place = URIRef("https://mustrd.org/coverage/run/test/term/onto.Place")
    assert (place, COV.role, COV.Structural) in g
    reasons = [str(r) for r in g.objects(place, COV.structuralReason)]
    assert any("isLocatedIn" in r for r in reasons)   # domain/range of the used property


CQ = Namespace("https://mustrd.org/competencyQuestion/")


def _cqdef(spec, question="Q?", name="a", missing=()):
    return {"id": f"http://ex/cq/{name}", "name": name, "question": question,
            "questions": [question], "source_file": None,
            "specs": [spec], "missing_specs": list(missing)}


def test_cq_nodes_and_assertions_in_graph():
    spec = {"name": "a.mustrd.ttl", "uri": "http://ex/a", "passed": True,
            "given": _graph(ONTO, DATA), "queries": [QUERY]}
    cov = compute_coverage([spec], ontology=_graph(ONTO), cq_defs=[_cqdef(spec)])
    g = coverage_graph(cov, [{"uri": "http://onto.org/"}], run_slug="test")
    cq = URIRef("http://ex/cq/a")
    assert (cq, RDF.type, CQ.CompetencyQuestion) in g
    assert (cq, CQ.question, Literal("Q?")) in g
    assert (cq, CQ.cqSpec, URIRef("http://ex/a")) in g
    # a cov:Assertion links the CQ to the passing test
    a = g.value(predicate=COV.onCompetencyQuestion, object=cq)
    assert a is not None
    assert (a, COV.onTest, URIRef("http://ex/a")) in g
    assert (a, COV.outcome, COV.Passed) in g
    # per-spec term usage is recorded (declared or not)
    assert (URIRef("http://ex/a"), COV.usesInData, URIRef("http://onto.org/City")) in g


def test_requires_ontology_links_to_the_ontology_iri():
    # The query matches its data only through the subClassOf hierarchy (data has a
    # City, query asks for Place), so the assertion links the ontology it needs —
    # an IRI, not a boolean.
    data = _graph("""@prefix onto: <http://onto.org/> . @prefix ex: <http://example.org/> .
    ex:r a onto:City .""")
    query = """PREFIX onto: <http://onto.org/> PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?x WHERE { ?x a/rdfs:subClassOf* onto:Place }"""
    spec = {"name": "a.mustrd.ttl", "uri": "http://ex/a", "passed": True,
            "given": data, "queries": [query]}
    cov = compute_coverage([spec], ontology=_graph(ONTO), cq_defs=[_cqdef(spec)])
    # term_ontology maps the driving class to its declaring ontology (authoritative)
    g = coverage_graph(cov, [{"uri": "http://onto.org/"}], run_slug="test",
                       term_ontology={"http://onto.org/Place": "http://onto.org/"})
    a = g.value(predicate=COV.onCompetencyQuestion, object=URIRef("http://ex/cq/a"))
    assert list(g.objects(a, COV.requiresOntology)) == [URIRef("http://onto.org/")]
    assert (a, COV.requiresOntology, Literal(True)) not in g   # not the old boolean


def test_duplicate_cqs_recorded_as_run_scoped_assertions():
    # Two CQ nodes share a question; each is the subject of a cov:Assertion that
    # links the peer with cov:duplicateOf — a run finding, NOT a triple on the CQ.
    spec = {"name": "a.mustrd.ttl", "uri": "http://ex/a", "passed": True,
            "given": _graph(ONTO, DATA), "queries": [QUERY]}
    defs = [_cqdef(spec, question="dupe?", name="x"),
            _cqdef(spec, question="dupe?", name="y")]
    g = coverage_graph(compute_coverage([spec], ontology=_graph(ONTO), cq_defs=defs),
                       [{"uri": "http://onto.org/"}], run_slug="test")
    x, y = URIRef("http://ex/cq/x"), URIRef("http://ex/cq/y")
    ax = g.value(predicate=COV.onCompetencyQuestion, object=x)   # the duplicate assertion for x
    assert (ax, RDF.type, COV.Assertion) in g and (ax, COV.duplicateOf, y) in g
    assert any((a, COV.duplicateOf, x) in g for a in g.subjects(COV.onCompetencyQuestion, y))
    assert (x, COV.duplicateOf, y) not in g          # not on the CQ node
    assert (x, COV.duplicate, Literal(True)) not in g


def test_run_carries_provenance():
    spec = {"name": "a.mustrd.ttl", "uri": "http://ex/a", "passed": True,
            "given": _graph(ONTO, DATA), "queries": [QUERY]}
    g = coverage_graph(compute_coverage([spec], ontology=_graph(ONTO)),
                       [{"uri": "http://onto.org/"}], run_slug="r1", git_sha="abc123",
                       repo_url="https://github.com/o/r",
                       started="2026-01-01T00:00:00+00:00",
                       commit_url="https://github.com/o/r/commit/abc123",
                       ci_run="https://github.com/o/r/actions/runs/9")
    run = URIRef("https://mustrd.org/coverage/run/r1")
    assert (run, RDF.type, COV.CoverageRun) in g
    assert (run, PROV.startedAtTime, Literal("2026-01-01T00:00:00+00:00", datatype=XSD.dateTime)) in g
    assert (run, COV.gitRepository, URIRef("https://github.com/o/r")) in g
    assert (run, COV.gitCommit, Literal("abc123")) in g
    assert (run, COV.gitCommitUrl, URIRef("https://github.com/o/r/commit/abc123")) in g
    assert (run, COV.ciRun, URIRef("https://github.com/o/r/actions/runs/9")) in g


def test_cq_only_graph_without_ontology():
    from mustrd.cq import cq_facts
    from mustrd.coverage_rdf import cq_graph
    spec = {"name": "a.mustrd.ttl", "uri": "http://ex/a", "passed": True,
            "given": _graph(DATA), "queries": [QUERY]}
    g = cq_graph(cq_facts([_cqdef(spec)]), run_slug="t")
    assert (URIRef("http://ex/cq/a"), RDF.type, CQ.CompetencyQuestion) in g
    assert (URIRef("http://ex/a"), COV.usesInData, URIRef("http://onto.org/City")) in g
    # a CQ-only graph carries no term-coverage measurements
    assert (None, RDF.type, COV.TermCoverage) not in g
