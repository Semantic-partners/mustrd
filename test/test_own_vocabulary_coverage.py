"""Coverage over a vocabulary mustrd normally treats as infrastructure.

`WELL_KNOWN` in ontology.py lists namespaces whose terms are the vocabulary a spec
is *written in* rather than the ontology under test — rdf:, rdfs:, owl:, and
mustrd's own must:/cq:. Filtering them out is right when the subject is somebody's
domain ontology: a spec file is full of `must:TestSpec` and `must:given`, and none
of that says anything about how well the tests exercise `place:City`.

But the list was absolute, so a vocabulary on it could never *be* the subject.
`declared_terms` filtered its own gate, so pointing an ontology path at
mustrd/model/ontology.ttl declared zero terms, `compute_coverage` returned None,
and the report said "no ontology was checked" — which is what stopped mustrd
measuring how much of its own model its own specs exercise.

"Well-known" is now relative to what is being measured: a namespace a graph
declares as its own (`owl:Ontology`) counts, whatever else it is.
"""
from pathlib import Path

from rdflib import Graph, URIRef

from mustrd.coverage import compute_coverage
from mustrd.ontology import (
    WELL_KNOWN, declared_terms, is_domain_term, measured_namespaces,
)

MUST = "https://mustrd.org/model/"
MUSTRD_ONTOLOGY = Path("mustrd/model/ontology.ttl")

# A spec file read as data — the only way mustrd's own vocabulary is ever queried,
# since specs *are* must: terms rather than asking about them.
SPEC_AS_DATA = """
@prefix must: <https://mustrd.org/model/> .
@prefix ex:   <http://example.org/spec/> .

ex:aSpec a must:TestSpec ;
    must:given [ a must:FileDataset ; must:file "data.ttl" ] ;
    must:when  [ a must:TextSparqlSource ; must:queryType must:SelectSparql ] .
"""

QUERY_OVER_SPECS = """PREFIX must: <https://mustrd.org/model/>
SELECT ?queryType WHERE {
  ?spec a must:TestSpec ; must:when ?when .
  ?when must:queryType ?queryType .
}"""


def _spec(passed=True):
    return {"name": "self.mustrd.ttl", "uri": "http://example.org/spec/aSpec",
            "passed": passed, "given": Graph().parse(data=SPEC_AS_DATA),
            "queries": [QUERY_OVER_SPECS], "source_file": "self.mustrd.ttl"}


def test_mustrd_namespace_is_still_infrastructure_by_default():
    """The default has to be unchanged, or every domain report fills up with the
    vocabulary the specs are written in."""
    assert MUST in WELL_KNOWN
    assert not is_domain_term(URIRef(MUST + "TestSpec"))
    assert not is_domain_term(URIRef("http://www.w3.org/2002/07/owl#Class"))


def test_a_namespace_being_measured_counts_as_domain():
    assert is_domain_term(URIRef(MUST + "TestSpec"), measured=(MUST,))
    # Only the namespace asked for — owl: is not smuggled in with it.
    assert not is_domain_term(URIRef("http://www.w3.org/2002/07/owl#Class"),
                              measured=(MUST,))


def test_an_ontology_declares_its_own_namespace():
    g = Graph().parse(MUSTRD_ONTOLOGY)
    assert measured_namespaces(g) == frozenset({MUST})


def test_declared_terms_finds_mustrds_own_model():
    """The gate that used to return nothing."""
    terms = declared_terms(Graph().parse(MUSTRD_ONTOLOGY))
    assert len(terms) > 40, "mustrd's own model declares more than 40 terms"
    assert terms[MUST + "TestSpec"] == "class"
    assert terms[MUST + "given"] == "property"


def test_coverage_over_mustrds_own_model():
    """The whole point: how much of mustrd's model do specs-about-specs exercise?"""
    ontology = Graph().parse(MUSTRD_ONTOLOGY)
    coverage = compute_coverage([_spec()], ontology=ontology)

    assert coverage is not None, "coverage bailed out — nothing declared"
    assert coverage["denominator"] > 40
    # The spec's data populates must:TestSpec / must:given / must:when, so those
    # are covered; the vast majority of the model is not, which is the useful part.
    assert 0 < coverage["covered"] < coverage["denominator"]
    covered = {r["iri"] for r in coverage["term_records"] if r["role"] == "covered"}
    assert MUST + "TestSpec" in covered
    assert MUST + "given" in covered


def test_a_domain_ontology_still_ignores_the_spec_vocabulary():
    """The regression that matters. The given graph here is a spec file, so it is
    full of must: terms — none of them may appear when the ontology under test is
    a domain vocabulary."""
    domain = Graph().parse(data="""
        @prefix owl:  <http://www.w3.org/2002/07/owl#> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        @prefix ex:   <http://example.org/shop#> .
        <http://example.org/shop#> a owl:Ontology .
        ex:Product a owl:Class ; rdfs:label "Product" .
    """)
    coverage = compute_coverage([_spec()], ontology=domain)
    assert coverage is not None
    measured_terms = {r["iri"] for r in coverage["term_records"]}
    assert measured_terms == {"http://example.org/shop#Product"}
    assert not any(t.startswith(MUST) for t in measured_terms)
    # Nor may they leak in as "used but not declared" — they are not the subject.
    assert not any(u["iri"].startswith(MUST) for u in coverage["undeclared"])
