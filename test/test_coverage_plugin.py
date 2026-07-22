"""End-to-end tests for the --term-coverage plugin wiring.

Runs the mustrd pytest plugin over the runnable example in
docs/examples/geography-example (the same fixtures the worked-example report
is generated from) and asserts the report it produces. Nested pytest.main
invocation mirrors test/test_pytest_mustrd.py.
"""
from pathlib import Path

import pytest

from mustrd.mustrdTestPlugin import MustrdTestPlugin

EXAMPLE = Path("docs/examples/geography-example")
CONFIG = EXAMPLE / "mustrd-config.ttl"


def _run(md_path, term_coverage):
    plugin = MustrdTestPlugin(
        str(md_path) if md_path else None, CONFIG, None, term_coverage=term_coverage
    )
    pytest.main([str(EXAMPLE), "-p", "no:cacheprovider"], plugins=[plugin])
    return plugin


def test_term_coverage_report_is_generated(tmp_path):
    md = tmp_path / "report.md"
    _run(md, term_coverage=True)
    text = md.read_text()

    # Ontologies section names BOTH ontologies measured against, with IRIs/desc.
    assert "these ontologies" in text  # plural header
    assert "place.ttl" in text and "http://example.org/place#" in text
    assert "governance.ttl" in text and "http://example.org/governance#" in text
    assert "A minimal vocabulary for places" in text

    # All three competency questions appear in the CQ table, which has both a
    # Test Status and a Coverage Status column.
    assert "In which country is Rotterdam?" in text
    assert "In what administrative division of what country is Rotterdam?" in text
    assert "Who is the mayor of Rotterdam?" in text
    assert "Test Status" in text and "Coverage Status" in text
    # 3 of the 4 tests in the suite are competency questions (region-lookup isn't).
    assert "3 of 4 tests are competency questions" in text
    # Coverage Status surfaces each CQ's undeclared terms; the clean CQ is ✅.
    assert "⚠️ undeclared: place:hasEconomicArea (input data)" in text
    assert "⚠️ undeclared: gov:appointedOn (SPARQL)" in text

    # 8/9 = 89%: 11 declared across both ontologies, two schema terms excluded
    # (place:Place and the ontology-level metadata place:basedOnStandard), and one
    # genuine gap (place:Region) dropping coverage below 100%.
    assert "8/9 terms used to answer the CQs = 89%" in text
    assert "11 declared; 2 structural/schema term(s) excluded" in text
    assert "place:Place" in text and "gov:Mayor" in text
    assert "place:basedOnStandard (property) — ontology property" in text
    # foaf:Person is referenced (Mayor's superclass / governs' domain) but not
    # declared here, so it is external and must not appear in coverage at all.
    assert "foaf:Person" not in text and "foaf" not in text

    # place:Region is exercised by no CQ. region-lookup DOES use it (data + SPARQL)
    # and passes, but has no must:competencyQuestion, so it is excluded from the CQ
    # table ("3 of 4" above) and doesn't count toward coverage — place:Region stays
    # unused. Its Status notes the non-CQ test and links to it.
    assert "place:Region (class) — declared in the ontology" in text
    region_row = next(ln for ln in text.splitlines() if ln.startswith("| place:Region "))
    assert "unused by CQ — exercised by" in region_row
    assert "region-lookup.mustrd.ttl](" in region_row
    # place:hasEconomicArea is used in the country data but not declared in
    # place.ttl, yet sits in the ontology's namespace -> flagged as
    # used-but-not-declared, listing the referencing CQ (linked to its spec) and
    # tagging it as referenced in the input data (not SPARQL).
    assert "## ⚠️ Used but not declared" in text
    # place:hasEconomicArea — used in the country data, tagged input data.
    assert "- **place:hasEconomicArea**" in text
    data_line = next(ln for ln in text.splitlines() if ln.strip().endswith("— input data"))
    assert "country-of-rotterdam.mustrd.ttl" in data_line and "](" in data_line
    # gov:appointedOn — referenced only in the mayor query (OPTIONAL), tagged SPARQL.
    assert "- **gov:appointedOn**" in text
    sparql_line = next(ln for ln in text.splitlines() if ln.strip().endswith("— SPARQL"))
    assert "mayor-of-rotterdam.mustrd.ttl" in sparql_line and "](" in sparql_line

    # The division CQ matches its data only via the class hierarchy (queries
    # AdministrativeDivision, data has Province), so it is flagged as needing the
    # ontology loaded; the country CQ (direct types) is not.
    assert "requires ontology to pass" in text
    bullets = [ln for ln in text.splitlines() if ln.startswith("- **")]
    division = next(ln for ln in bullets if ln.startswith("- **division-and-country"))
    country = next(ln for ln in bullets if ln.startswith("- **country-of-rotterdam"))
    assert "requires ontology to pass" in division
    assert "requires ontology to pass" not in country


def test_md_without_term_coverage_is_the_result_list(tmp_path):
    # Additive behaviour: without --term-coverage, --md keeps its pre-existing
    # (master) form — a ResultList of every test — and none of the coverage
    # report's sections appear. The competency-question table and coverage are
    # exclusive to --term-coverage.
    md = tmp_path / "report.md"
    _run(md, term_coverage=False)
    text = md.read_text()
    assert "total:" in text  # ResultList summary line
    assert "# Ontologies Report" not in text
    assert "## Competency Questions" not in text
    assert "Ontology term coverage" not in text
    assert "Coverage Status" not in text


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
    assert "test/test_config_local.ttl" in msg
