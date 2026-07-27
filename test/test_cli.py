"""Tests for the standalone `mustrd` CLI (mustrd.cli).

Drives the same runnable example the pytest plugin test uses
(docs/examples/geography-example) and asserts the CLI produces the same report
content WITHOUT pytest, plus the JSON-LD serialization the viewer consumes.
"""
import os
import subprocess
import sys
import textwrap
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


@pytest.mark.parametrize("console_encoding", ["cp1252", "ascii"])
def test_report_survives_a_non_utf8_console(console_encoding):
    """The coverage report is not ASCII — the term tree uses ↳ and ▸. A Windows
    console is cp1252 by default, where printing it raised UnicodeEncodeError and
    took the command down. Reproduced anywhere via PYTHONIOENCODING."""
    proc = subprocess.run(
        [sys.executable, "-m", "mustrd.cli", "report", "--config", CONFIG,
         "--term-coverage", "--cq"],
        env={**os.environ, "PYTHONIOENCODING": console_encoding},
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert proc.returncode == 0, proc.stderr
    assert "UnicodeEncodeError" not in proc.stderr
    assert "terms exercised by the tests" in proc.stdout


def test_importing_mustrd_leaves_the_hosts_logging_alone():
    """mustrd is a library: importing it must not configure, re-level or remove
    anything on the root logger. It used to call basicConfig and then blank the
    root handlers, silently deleting the logging setup of whatever imported it —
    mustrd's own CLI included, which is why `mustrd run` printed nothing.

    Run in a subprocess: the check is about what happens at *import* time, and
    reloading these modules in-process would rebuild the Spec classes the rest of
    the suite has already imported.
    """
    program = textwrap.dedent("""
        import logging, io
        stream = io.StringIO()
        logging.basicConfig(stream=stream, level=logging.INFO, format="%(message)s")
        before = list(logging.getLogger().handlers)
        logging.getLogger("host.app").info("hello")
        import mustrd.mustrd, mustrd.spec_component, mustrd.mustrdTestPlugin  # noqa
        root = logging.getLogger()
        assert root.handlers == before, "a root handler was removed or replaced"
        assert root.level == logging.INFO, f"root level became {root.level}"
        logging.getLogger("host.app").info("still here")
        assert stream.getvalue().split() == ["hello", "still", "here"], stream.getvalue()
        print("ok")
    """)
    proc = subprocess.run([sys.executable, "-c", program],
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip().endswith("ok")


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
