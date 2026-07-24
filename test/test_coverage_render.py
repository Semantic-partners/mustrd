"""Rendering-level tests: the Coverage Report Markdown is a pure function of the
coverage RDF graph (+ the ontology, for the subClassOf tree).

Fixture in: the committed example graph and its ontologies. Out: the Markdown
Coverage Report. This exercises the renderer without recomputing coverage.
"""
from pathlib import Path

from rdflib import Graph

from mustrd.coverage_render import coverage_context
from mustrd.cq_render import cq_report
from mustrd.TestResult import render_term_coverage, render_cq_table, render_per_cq
from mustrd.mustrdTestPlugin import _link_report_refs, _link_href

EXAMPLE = Path("docs/examples/geography-example")
GRAPH_TTL = EXAMPLE / "report" / "term-coverage-example.ttl"
ONTOLOGY_FILES = [EXAMPLE / "ontology" / "place.ttl",
                  EXAMPLE / "ontology" / "governance.ttl"]


def _render():
    graph = Graph()
    graph.parse(str(GRAPH_TTL), format="turtle")
    ontology = Graph()
    for f in ONTOLOGY_FILES:
        ontology.parse(str(f))
    ctx = coverage_context(graph, ontology)
    _link_report_refs(ctx, _link_href("."))   # populate report links
    return ctx, render_term_coverage(ctx)


def test_headline_numbers_render_from_the_graph():
    ctx, md = _render()
    assert ctx["covered"] == 8 and ctx["denominator"] == 9
    assert "8/9 terms exercised by the tests = 89%" in md
    assert "By a competency question: 7/9 = 78%" in md


def test_matrix_reflects_roles_from_the_graph():
    _, md = _render()
    # subClassOf tree (built from the ontology) with graph-sourced verdicts.
    assert "↳ place:AdministrativeDivision" in md
    ad_row = next(ln for ln in md.splitlines() if "place:AdministrativeDivision" in ln
                  and ln.startswith("|"))
    assert "❌ query only" in ad_row
    # per-test sub-row for a covered term
    assert "▸ place:isLocatedIn" in md
    assert any(ln.strip().startswith("| &nbsp;") and "• [" in ln for ln in md.splitlines())


def test_structural_and_undeclared_sections_render_from_the_graph():
    _, md = _render()
    assert "### Structural terms (excluded from coverage)" in md
    assert "place:Place" in md and "isLocatedIn" in md          # structural reason
    assert "### ⚠️ Used but not declared" in md
    assert "place:hasEconomicArea" in md and "gov:appointedOn" in md


def test_cq_report_renders_from_the_graph():
    # The CQ half is a pure function of the graph too.
    graph = Graph()
    graph.parse(str(GRAPH_TTL), format="turtle")
    ontology = Graph()
    for f in ONTOLOGY_FILES:
        ontology.parse(str(f))
    cqr = cq_report(graph, ontology, _link_href("."))
    assert cqr["has_ontology"]
    questions = {c["question"] for c in cqr["per_cq"]}
    assert "Who is the mayor of Rotterdam?" in questions
    assert "What is the population of Rotterdam?" in questions   # the test-less CQ
    table = render_cq_table(cqr["per_cq"], show_coverage=True)
    assert "In which country is Rotterdam?" in table
    pop = next(c for c in cqr["per_cq"] if "population" in c["question"])
    assert pop["has_test"] is False
    detail = render_per_cq(cqr["per_cq"], unchecked=False)
    assert "requires ontology to pass" in detail          # the division CQ
