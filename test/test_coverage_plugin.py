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

    # Ontologies section names the file measured against and its IRI/description.
    assert "geography.ttl" in text
    assert "http://example.org/place#" in text
    assert "A minimal vocabulary for places" in text

    # Both competency questions appear in the CQ table.
    assert "In which country is Rotterdam?" in text
    assert "In what administrative division of what country is Rotterdam?" in text

    # 6/6 = 100%: 8 declared, two schema terms excluded (place:Place and the
    # ontology-level metadata property place:basedOnStandard), no gaps.
    assert "6/6 terms used to answer the CQs = 100%" in text
    assert "8 declared; 2 structural/schema term(s) excluded" in text
    assert "place:Place" in text
    assert "place:basedOnStandard (property) — ontology property" in text
    assert "_none — every declared term is exercised or structural_" in text


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
