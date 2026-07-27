"""Tests for the standalone `mustrd` CLI (mustrd.cli).

Drives the same runnable example the pytest plugin test uses
(docs/examples/geography-example) and asserts the CLI produces the same report
content WITHOUT pytest, plus the JSON-LD serialization the viewer consumes.
"""
from pathlib import Path

import pytest
from rdflib import Graph

from mustrd.cli import main

EXAMPLE = Path("docs/examples/geography-example")
CONFIG = str(EXAMPLE / "mustrd-config.ttl")


def test_report_matches_plugin_content(tmp_path):
    md = tmp_path / "report.md"
    ttl = tmp_path / "coverage.ttl"
    jsonld = tmp_path / "run.jsonld"
    rc = main([
        "report", "--config", CONFIG, "--term-coverage", "--cq",
        "--md", str(md), "--term-coverage-rdf", str(ttl),
        "--term-coverage-jsonld", str(jsonld),
    ])
    assert rc == 0

    text = md.read_text(encoding="utf-8")
    # Same assembled report the plugin produces (see test_coverage_plugin.py).
    assert "# Ontologies Report" in text
    assert "## Coverage Report" in text
    assert "## Competency Questions Report" in text
    assert "8/9 terms exercised by the tests = 89%" in text
    assert "By a competency question: 7/9 = 78%" in text
    assert "Who is the mayor of Rotterdam?" in text

    # The JSON-LD is the same canonical graph as the Turtle, just reserialized.
    j = Graph().parse(jsonld, format="json-ld")
    t = Graph().parse(ttl, format="turtle")
    assert len(j) == len(t) > 0
    assert j.isomorphic(t)


def test_run_returns_zero_when_all_pass():
    assert main(["run", "--config", CONFIG]) == 0


def test_run_shows_the_review_table(capsys):
    """mustrd.mustrd drops the root logger's handlers when imported, which used to
    leave `mustrd run` completely silent — the review table is logged, not printed."""
    assert main(["run", "--config", CONFIG]) == 0
    out = capsys.readouterr().out
    assert "Result Overview" in out
    assert "Spec Uris / triple stores" in out
    assert "SpecPassed" in out
    assert "0 failures" in out


@pytest.mark.parametrize("bad", ["no-such-config.ttl", "docs/examples"])
def test_bad_config_fails_with_a_usage_message(bad, capsys):
    """A wrong --config is the easiest mistake to make (paths inside a config are
    relative to the config file), so it must not surface as an rdflib traceback."""
    with pytest.raises(SystemExit) as exc:
        main(["report", "--config", bad, "--viewer", "unused.html"])
    message = str(exc.value)
    assert message.startswith("mustrd: ")
    assert bad in message
    assert not Path("unused.html").exists()
