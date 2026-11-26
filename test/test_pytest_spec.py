"""Specs written in code (mustrd.pytest_spec): the `spec` fixture and mustrd_spec.cq(...).

Runs the code specs in test/code-specs through the plugin in a nested pytest run (as
test_coverage_plugin.py does), and checks the coverage and competency questions it reports.
The specs live in the repo, not in tmp_path, so coverage records them at a path that exists in CI.
"""
from pathlib import Path

import pytest

from mustrd.mustrdTestPlugin import MustrdTestPlugin

CODE_SPECS = Path(__file__).parent / "code-specs"


def _run(tmp_path):
    md = tmp_path / "report.md"
    plugin = MustrdTestPlugin(str(md), CODE_SPECS / "mustrd-config.ttl", None, term_coverage=True, cq=True)
    exit_code = pytest.main([str(CODE_SPECS / "code_specs.py"), "-p", "no:cacheprovider"], plugins=[plugin])
    return exit_code, md.read_text(encoding="utf-8")


def test_code_specs_report_coverage_and_competency_questions(tmp_path):
    exit_code, text = _run(tmp_path)
    assert exit_code == pytest.ExitCode.TESTS_FAILED  # test_runtimes_fails fails, on purpose
    # Only the passing spec counts: ex:Movie and ex:title, not ex:runtime.
    assert "**Overall: 2/3 terms exercised by the tests = 67%**" in text
    # Both questions are listed without a CQ file, each linked to its test.
    assert "2 competency questions — 2 with a test, 0 without." in text
    assert "What are the movie titles?" in text and "test_titles" in text
    assert "How long is each movie?" in text and "test_runtimes_fails" in text
