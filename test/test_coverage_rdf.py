"""Data-level tests: compute_coverage -> coverage_graph emits the right triples.

The RDF graph is the canonical output of a coverage run; here we assert the
*data* it contains, independently of how it's later rendered.
"""
from rdflib import Graph, URIRef, Namespace, RDF, XSD, Literal

from mustrd.coverage import compute_coverage
from mustrd.coverage_rdf import coverage_graph

COV = Namespace("https://mustrd.org/coverage/")
DQV = Namespace("http://www.w3.org/ns/dqv#")

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
