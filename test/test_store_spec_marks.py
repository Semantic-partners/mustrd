"""A spec that reads an existing store has no input data by design.

Its terms are never "in input data", so the term table must not mark that with
❌, nor call a term it alone queries "❌ query only". A spec WITH input data that
fails to populate a term it queries keeps the ❌: that one is a real gap.
"""
import re

from rdflib import Graph

from mustrd.reporting import ReportOptions
from mustrd.runner import static_coverage
from mustrd.namespace import COV

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

# Reads a store: names City and isLocatedIn, has no `given`.
STORE_SPEC = """
@prefix must: <https://mustrd.org/model/> .
@prefix ex:   <http://ex/> .
ex:storeCities a must:TestSpec ;
    must:given [ a must:InheritedDataset ] ;
    must:when  [ a must:TextSparqlSource ;
                 must:queryText "PREFIX onto: <http://onto.org/> SELECT ?x WHERE { ?x a onto:City ; onto:isLocatedIn ?y }" ;
                 must:queryType must:SelectSparql ] ;
    must:then  [ a must:EmptyTable ] .
"""

# Has input data that does not populate Country, which its query names.
DATA_SPEC = """
@prefix must: <https://mustrd.org/model/> .
@prefix rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix ex:   <http://ex/> .
ex:dataCountries a must:TestSpec ;
    must:given [ a must:StatementsDataset ;
                 must:hasStatement [ a rdf:Statement ;
                     rdf:subject ex:s ; rdf:predicate ex:p ; rdf:object ex:o ] ] ;
    must:when  [ a must:TextSparqlSource ;
                 must:queryText "PREFIX onto: <http://onto.org/> SELECT ?x WHERE { ?x a onto:Country }" ;
                 must:queryType must:SelectSparql ] ;
    must:then  [ a must:EmptyTable ] .
"""

CONFIG = """
@prefix : <https://mustrd.org/mustrdTest/> .
:suite a :MustrdTest ;
    :hasSpecPath "specs" ; :hasDataPath "data" ;
    :hasOntologyPath "onto.ttl" ; :hasPytestPath "suite" .
"""


def _report(tmp_path):
    (tmp_path / "specs").mkdir()
    (tmp_path / "data").mkdir()
    (tmp_path / "specs" / "store.mustrd.ttl").write_text(STORE_SPEC, encoding="utf-8")
    (tmp_path / "specs" / "data.mustrd.ttl").write_text(DATA_SPEC, encoding="utf-8")
    (tmp_path / "onto.ttl").write_text(ONTO, encoding="utf-8")
    (tmp_path / "mustrd-config.ttl").write_text(CONFIG, encoding="utf-8")
    md, ttl = tmp_path / "out.md", tmp_path / "out.ttl"
    static_coverage(tmp_path / "mustrd-config.ttl",
                    ReportOptions(md_path=str(md), term_coverage=True,
                                  term_coverage_rdf=str(ttl)))
    return md.read_text(encoding="utf-8"), Graph().parse(ttl, format="turtle")


def _row(md, term):
    """The cells of the term table row for `term` (not its • sub-rows)."""
    for line in md.splitlines():
        if re.search(rf"\|\s*(&nbsp;)*(↳ |▸ )?{re.escape(term)}\s*\|", line):
            return [c.strip() for c in line.strip().strip("|").split("|")]
    raise AssertionError(f"no row for {term}")


def _subrow(md, spec_name):
    for line in md.splitlines():
        if f"• [{spec_name}]" in line:
            return [c.strip() for c in line.strip().strip("|").split("|")]
    raise AssertionError(f"no sub-row for {spec_name}")


def test_store_only_terms_are_not_crossed(tmp_path):
    md, _ = _report(tmp_path)
    for term in ("onto:City", "onto:isLocatedIn"):
        cells = _row(md, term)
        assert cells[2] == "—", cells          # In input data
        assert cells[3] == "✅", cells          # In SPARQL
        assert cells[5] == "🔎 queried", cells  # Test Term Coverage
    assert _subrow(md, "store.mustrd.ttl")[2] == "—"


def test_a_spec_with_data_that_misses_a_term_keeps_the_cross(tmp_path):
    md, _ = _report(tmp_path)
    cells = _row(md, "onto:Country")
    assert cells[2] == "❌"
    assert cells[5] == "❌ query only"
    assert _subrow(md, "data.mustrd.ttl")[2] == "❌"


def test_headlines_and_coverage_rule_unchanged(tmp_path):
    md, _ = _report(tmp_path)
    assert "**Overall: 0/3 terms exercised by the tests = 0%**" in md
    assert "**Queried: 3/3 terms named by a query = 100%**" in md


CQ = """
@prefix cq: <https://mustrd.org/competencyQuestion/> .
@prefix ex: <http://ex/> .
ex:citiesCQ a cq:CompetencyQuestion ;
    cq:question "Which cities are located somewhere?" ;
    cq:cqSpec ex:storeCities .
"""

# A CQ's cq:cqSpec must name a spec in its own file.
CQ_DATA = """
@prefix cq: <https://mustrd.org/competencyQuestion/> .
@prefix ex: <http://ex/> .
ex:countriesCQ a cq:CompetencyQuestion ;
    cq:question "Which countries are there?" ;
    cq:cqSpec ex:dataCountries .
"""


def test_cq_gaps_say_queried_for_store_only_terms(tmp_path):
    (tmp_path / "specs").mkdir()
    (tmp_path / "data").mkdir()
    (tmp_path / "specs" / "store.mustrd.ttl").write_text(STORE_SPEC + CQ, encoding="utf-8")
    (tmp_path / "specs" / "data.mustrd.ttl").write_text(DATA_SPEC + CQ_DATA, encoding="utf-8")
    (tmp_path / "onto.ttl").write_text(ONTO, encoding="utf-8")
    (tmp_path / "mustrd-config.ttl").write_text(CONFIG, encoding="utf-8")
    md = tmp_path / "out.md"
    static_coverage(tmp_path / "mustrd-config.ttl",
                    ReportOptions(md_path=str(md), term_coverage=True, cq=True))
    gaps = md.read_text(encoding="utf-8").split("### Not used by any CQ", 1)[1]
    city = next(line for line in gaps.splitlines() if line.startswith("- onto:City "))
    country = next(line for line in gaps.splitlines() if line.startswith("- onto:Country "))
    assert "(**queried**)" in city and "query-only" not in city
    assert "(**query-only**)" in country


def test_reads_store_is_on_the_spec_in_the_graph(tmp_path):
    _, g = _report(tmp_path)
    reads = {str(s) for s in g.subjects(COV.readsStore, None)}
    assert reads == {"http://ex/storeCities"}
