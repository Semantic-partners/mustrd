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

    # All three competency questions appear in the CQ table.
    assert "In which country is Rotterdam?" in text
    assert "In what administrative division of what country is Rotterdam?" in text
    assert "Who is the mayor of Rotterdam?" in text

    # 8/8 = 100%: 10 declared across both ontologies, two schema terms excluded
    # (place:Place and the ontology-level metadata place:basedOnStandard), no gaps.
    assert "8/8 terms used to answer the CQs = 100%" in text
    assert "10 declared; 2 structural/schema term(s) excluded" in text
    assert "place:Place" in text and "gov:Mayor" in text
    assert "place:basedOnStandard (property) — ontology property" in text
    # foaf:Person is referenced (Mayor's superclass / governs' domain) but not
    # declared here, so it is external and must not appear in coverage at all.
    assert "foaf:Person" not in text and "foaf" not in text
    assert "_none — every declared term is exercised or structural_" in text

    # The division CQ matches its data only via the class hierarchy (queries
    # AdministrativeDivision, data has Province), so it is flagged as needing the
    # ontology loaded; the country CQ (direct types) is not.
    assert "requires ontology to pass" in text
    bullets = [ln for ln in text.splitlines() if ln.startswith("- **")]
    division = next(ln for ln in bullets if ln.startswith("- **division-and-country"))
    country = next(ln for ln in bullets if ln.startswith("- **country-of-rotterdam"))
    assert "requires ontology to pass" in division
    assert "requires ontology to pass" not in country


def test_md_without_term_coverage_is_just_the_cq_table(tmp_path):
    # Without --term-coverage the report stays the plain Competency Questions
    # table — no ontology required, no coverage section (additive behaviour).
    md = tmp_path / "report.md"
    _run(md, term_coverage=False)
    text = md.read_text()
    assert "## Competency Questions" in text
    assert "In which country is Rotterdam?" in text
    assert "Ontology term coverage" not in text
    assert "# Ontologies Report" not in text


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
