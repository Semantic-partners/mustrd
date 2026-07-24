"""End-to-end tests for the --term-coverage / --cq plugin wiring.

Runs the mustrd pytest plugin over the runnable example in
docs/examples/geography-example (the same fixtures the worked-example report
is generated from) and asserts the report it produces. Nested pytest.main
invocation mirrors test/test_pytest_mustrd.py.
"""
import os
from pathlib import Path

import pytest

from mustrd.mustrdTestPlugin import MustrdTestPlugin

EXAMPLE = Path("docs/examples/geography-example")
CONFIG = EXAMPLE / "mustrd-config.ttl"


def _run(md_path, term_coverage=False, cq=False):
    plugin = MustrdTestPlugin(
        str(md_path) if md_path else None, CONFIG, None,
        term_coverage=term_coverage, cq=cq,
    )
    pytest.main([str(EXAMPLE), "-p", "no:cacheprovider"], plugins=[plugin])
    return plugin


def test_full_report_term_coverage_and_cq(tmp_path):
    md = tmp_path / "report.md"
    _run(md, term_coverage=True, cq=True)
    text = md.read_text(encoding="utf-8")

    # Two sub-reports under the top title.
    assert "# Ontologies Report" in text
    assert "## Coverage Report" in text
    assert "## Competency Questions Report" in text
    # Ontologies section names BOTH ontologies, with IRIs/description.
    assert "these ontologies" in text
    assert "place.ttl" in text and "http://example.org/place#" in text
    assert "governance.ttl" in text and "http://example.org/governance#" in text

    # CQ-first table: four CQ nodes (3 with a test, 1 without), Test + Coverage
    # Status columns. The test-less CQ shows an em-dash.
    assert "In which country is Rotterdam?" in text
    assert "Who is the mayor of Rotterdam?" in text
    assert "Test Status" in text and "Coverage Status" in text
    assert "4 competency questions — 3 with a test, 1 without." in text
    assert "What is the population of Rotterdam?" in text  # the test-less CQ
    cq_table = text.split("### Competency Questions", 1)[1].split("\n### ", 1)[0]
    pop_row = next(ln for ln in cq_table.splitlines() if "population of Rotterdam" in ln)
    assert pop_row.endswith("| — | — | — |")  # no test, no status
    assert "Duplicate competency questions" not in text
    assert "⚠️ undeclared: place:hasEconomicArea (input data)" in text
    assert "⚠️ undeclared: gov:appointedOn (SPARQL)" in text

    # Two coverage metrics, data-based: all tests 8/9=89%, CQs 7/9=78%.
    # place:AdministrativeDivision is query-only (named by the division query but
    # never instantiated), so it is NOT covered.
    assert "8/9 terms exercised by the tests = 89%" in text
    assert "By a competency question: 7/9 = 78%" in text
    assert "11 declared; 2 structural term(s) excluded" in text

    # Class rows form a subClassOf tree. The external superclass foaf:Person is a
    # root row (marked external + schema); gov:Mayor is indented under it.
    foaf_row = next(ln for ln in text.splitlines() if ln.startswith("| foaf:Person "))
    assert "· _external_" in foaf_row and foaf_row.endswith("| 🔧 structural | 🔧 structural |")
    assert "↳ gov:Mayor" in text          # subclass indented under foaf:Person
    assert "↳↳ " not in text              # (indent uses nbsp, not repeated glyphs)
    assert "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;↳ place:Province" in text  # depth-2
    # Properties nest (▸) under their rdfs:domain class.
    assert "▸ place:isLocatedIn" in text  # domain place:Place
    assert "▸ gov:governs" in text        # domain foaf:Person
    # place:basedOnStandard has no domain -> trails at top level (no connector).
    assert next(ln for ln in text.splitlines() if "place:basedOnStandard" in ln).startswith("| place:basedOnStandard ")

    # place:Region: term row carries the status; a • sub-row links the covering
    # test with that test's own input-data / SPARQL contribution.
    region_row = next(ln for ln in text.splitlines() if "↳ place:Region " in ln)
    assert region_row.endswith("| ✅ covered | ❌ unused |")  # covered, but no CQ covers it
    region_sub = next(ln for ln in text.splitlines() if "• [region-lookup.mustrd.ttl](" in ln)
    assert region_sub.count("✅") == 2  # this test contributes both data + SPARQL
    place_row = next(ln for ln in text.splitlines() if ln.startswith("| place:Place "))
    assert place_row.endswith("| 🔧 structural | 🔧 structural |")
    # place:AdministrativeDivision: query-only -> a gap, marked "❌ query only".
    ad_row = next(ln for ln in text.splitlines() if "place:AdministrativeDivision" in ln and ln.startswith("|"))
    assert "❌ query only" in ad_row
    # Not covered by any test lists the query-only term (with the move-it hint).
    assert "### Not covered by any test" in text
    gaps = text.split("### Not covered by any test", 1)[1].split("\n### ", 1)[0]
    assert "place:AdministrativeDivision" in gaps and "query-only" in gaps
    assert "### Not used by any CQ" in text
    cq_gaps = text.split("### Not used by any CQ", 1)[1].split("\n### ", 1)[0]
    assert "place:Region" in cq_gaps
    assert "region-lookup.mustrd.ttl](" in cq_gaps  # links the non-CQ test that uses it
    assert "place:basedOnStandard (property) — ontology property" in text

    # TBox-in-data hint: the division fixture declares schema in its given.
    assert "### ⚠️ TBox axioms in test data" in text
    tbox = text.split("### ⚠️ TBox axioms in test data", 1)[1].split("\n## ", 1)[0]
    assert "division-and-country-of-rotterdam.mustrd.ttl](" in tbox
    assert "place:Province rdfs:subClassOf place:AdministrativeDivision" in tbox

    # Used but not declared: one input-data term, one SPARQL term, each linked.
    assert "### ⚠️ Used but not declared" in text
    data_line = next(ln for ln in text.splitlines() if ln.strip().endswith("— input data"))
    assert "country-of-rotterdam.mustrd.ttl" in data_line and "](" in data_line
    sparql_line = next(ln for ln in text.splitlines() if ln.strip().endswith("— SPARQL"))
    assert "mayor-of-rotterdam.mustrd.ttl" in sparql_line and "](" in sparql_line

    # Per-CQ: the division CQ needs the class hierarchy; the country CQ doesn't.
    # The flag now sits on the test sub-line under each question bullet.
    assert "requires ontology to pass" in text
    per_cq = text.split("### Per competency question", 1)[1]
    division = per_cq.split("administrative division", 1)[1].split("- **", 1)[0]
    country = per_cq.split("In which country is Rotterdam?", 1)[1].split("- **", 1)[0]
    assert "requires ontology to pass" in division
    assert "requires ontology to pass" not in country
    # The test-less CQ is listed with no linked test.
    assert "_no linked test_" in per_cq


def test_term_coverage_alone_has_no_cq_sections(tmp_path):
    # --term-coverage without --cq: coverage over all tests, test-framed, and
    # none of the competency-question extras.
    md = tmp_path / "report.md"
    _run(md, term_coverage=True, cq=False)
    text = md.read_text(encoding="utf-8")
    assert "## Coverage Report" in text
    assert "8/9 terms exercised by the tests = 89%" in text
    assert "### Not covered by any test" in text
    # No CQ report / overlay.
    assert "Competency Questions Report" not in text
    assert "By a competency question" not in text
    assert "CQ Term Coverage" not in text
    assert "### Per competency question" not in text
    assert "Not used by any CQ" not in text


def test_cq_alone_has_no_ontology_sections(tmp_path):
    # --cq without --term-coverage: CQ table + per-CQ, no ontology check.
    md = tmp_path / "report.md"
    _run(md, cq=True)
    text = md.read_text(encoding="utf-8")
    assert "# Competency Questions Report" in text  # standalone -> H1
    assert "### Competency Questions" in text
    assert "In which country is Rotterdam?" in text
    assert "### Per competency question" in text
    assert "No ontology was checked" in text  # unchecked note
    # No coverage/ontology sections, and no Coverage Status column.
    assert "## Coverage Report" not in text
    assert "Term Coverage" not in text
    assert "# Ontologies Report" not in text
    assert "Coverage Status" not in text
    # Unchecked list includes an undeclared term (no ontology to filter it out).
    assert "place:hasEconomicArea" in text


def test_md_without_flags_is_the_result_list(tmp_path):
    # Additive: plain --md (no --term-coverage, no --cq) keeps the master
    # ResultList of every test; no report sections.
    md = tmp_path / "report.md"
    _run(md)
    text = md.read_text(encoding="utf-8")
    assert "total:" in text  # ResultList summary line
    assert "# Ontologies Report" not in text
    assert "Competency Questions Report" not in text
    assert "Term Coverage" not in text


def test_github_actions_links_are_absolute(tmp_path, monkeypatch):
    # In a GitHub Actions run the report is shown in the job summary (rendered on
    # the Actions page), where report-relative links don't resolve — so links
    # become absolute URLs into the repo on the GitHub web UI.
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_SERVER_URL", "https://github.com")
    monkeypatch.setenv("GITHUB_REPOSITORY", "Semantic-partners/mustrd")
    monkeypatch.setenv("GITHUB_SHA", "abc123")
    monkeypatch.setenv("GITHUB_WORKSPACE", os.getcwd())
    md = tmp_path / "report.md"
    _run(md, term_coverage=True, cq=True)
    text = md.read_text(encoding="utf-8")

    base = "https://github.com/Semantic-partners/mustrd/blob/abc123/"
    # an ontology file and a spec file both link to the GitHub web UI
    assert f"{base}docs/examples/geography-example/ontology/place.ttl" in text
    assert f"{base}docs/examples/geography-example/specs/mayor-of-rotterdam.mustrd.ttl" in text
    # no report-relative links survive
    assert "](../specs/" not in text
    assert "](ontology/" not in text


def test_missing_ontology_path_fails_early():
    # --term-coverage against a config without :hasOntologyPath aborts during
    # collection with a helpful message, before any tests run.
    plugin = MustrdTestPlugin(
        None, Path("test/test_config_local.ttl"), None, term_coverage=True
    )
    with pytest.raises(pytest.UsageError) as exc:
        plugin._resolve_ontology_paths_or_fail()
    msg = str(exc.value)
    assert "hasOntologyPath" in msg
    # normalise separators: the message shows a native path (backslashes on Windows)
    assert "test/test_config_local.ttl" in msg.replace("\\", "/")
