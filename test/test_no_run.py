"""`--no-run`: specs are collected and reported on, never executed.

A non-run names terms; it proves nothing. So it must neither read as a pass
(`cov:Covered`, a coverage ratio) nor as a failure (0%, `cov:Failed`).
"""
from pathlib import Path

import pytest
from rdflib import Graph

from mustrd import runner
from mustrd.cli import main
from mustrd.namespace import COV, DQV

EXAMPLE = Path("docs/examples/geography-example").resolve()


@pytest.fixture
def report(monkeypatch, tmp_path, capsys):
    def boom(spec):
        raise AssertionError("--no-run executed a spec")

    monkeypatch.setattr(runner, "run_spec", boom)
    monkeypatch.chdir(EXAMPLE)
    ttl, md, results = tmp_path / "c.ttl", tmp_path / "r.md", tmp_path / "res.ttl"
    code = main(["report", "--config", "mustrd-config.ttl", "--term-coverage", "--cq",
                 "--no-run", "--term-coverage-rdf", str(ttl), "--md", str(md),
                 "--results-rdf", str(results)])
    return {"code": code, "graph": Graph().parse(ttl, format="turtle"),
            "md": md.read_text(encoding="utf-8"), "results": results,
            "out": capsys.readouterr().out}


def test_no_spec_runs_and_the_build_passes(report):
    assert report["code"] == 0


def test_terms_are_referenced_not_covered(report):
    g = report["graph"]
    assert (None, COV.role, COV.Referenced) in g
    assert (None, COV.role, COV.Covered) not in g


def test_the_ratio_is_not_published_as_coverage(report):
    g = report["graph"]
    assert (None, DQV.isMeasurementOf, COV.termReferenceByTests) in g
    assert (None, DQV.isMeasurementOf, COV.termCoverageByTests) not in g


def test_a_competency_question_is_not_failed_by_a_spec_that_never_ran(report):
    g = report["graph"]
    assert (None, COV.outcome, COV.Failed) not in g
    assert (None, COV.outcome, COV.Passed) not in g
    assert (None, COV.outcome, COV.NotRun) in g


def test_the_report_says_nothing_was_proved(report):
    md = report["md"]
    assert "Not run: 8/" in md
    assert "⏸️ referenced" in md
    assert "✅ covered" not in md.split("#### How to read this table")[0]


def test_the_summary_counts_collected_specs(report):
    assert "5 specs collected, not run; 0 skipped or invalid" in report["out"]


def test_no_results_graph_claims_outcomes(report):
    results = report["results"]
    if results.exists():
        assert (None, COV.outcome, None) not in Graph().parse(results, format="turtle")
