"""Golden test: the committed geography-example report is up to date.

`docs/examples/geography-example/report/term-coverage-example.md` is a generated
artifact checked into the repo (so it renders on GitHub and documents the
feature). If a change alters the report, the committed copy must be regenerated
and committed. This test regenerates it in the same environment it was committed
from — from the example directory, with the GitHub-Actions link/slug env removed
so links are relative and the run slug is 'local' — and fails with a diff (and
the command to run) if the committed copy is stale.

Runs in CI (via `pytest test/`) and locally, so a stale report is caught before
merge. The RDF twin (.ttl) isn't byte-compared here — rdflib's Turtle
serialisation order can vary across versions — it's covered by test_coverage_rdf
/ test_coverage_render and uploaded as a CI artifact.
"""
import difflib
from pathlib import Path

import pytest

from mustrd.mustrdTestPlugin import MustrdTestPlugin

EXAMPLE = Path("docs/examples/geography-example").resolve()
COMMITTED_MD = Path("report/term-coverage-example.md")   # relative to EXAMPLE

REGEN_CMD = (
    "(cd docs/examples/geography-example && \\\n"
    "   pytest . --mustrd --config=mustrd-config.ttl --term-coverage --cq \\\n"
    "          --md=report/term-coverage-example.md \\\n"
    "          --term-coverage-rdf=report/term-coverage-example.ttl)"
)


def test_committed_example_report_is_up_to_date(monkeypatch):
    # Reproduce the exact environment the committed file was generated in: from
    # the example dir, with the GitHub-Actions link/slug env removed. Write the
    # regenerated report into the same report/ directory (a temp name) so its
    # links are relative to the same base as the committed copy.
    for var in ("GITHUB_ACTIONS", "GITHUB_SHA", "GITHUB_REPOSITORY",
                "GITHUB_SERVER_URL", "GITHUB_WORKSPACE"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.chdir(EXAMPLE)

    md = COMMITTED_MD.parent / "__golden_check__.md"
    plugin = MustrdTestPlugin(str(md), Path("mustrd-config.ttl"), None,
                              term_coverage=True, cq=True)
    try:
        pytest.main([".", "-p", "no:cacheprovider"], plugins=[plugin])
        generated = md.read_text()
    finally:
        md.unlink(missing_ok=True)

    committed = COMMITTED_MD.read_text()
    if generated != committed:
        diff = "".join(difflib.unified_diff(
            committed.splitlines(True), generated.splitlines(True),
            fromfile="committed", tofile="regenerated"))
        pytest.fail(
            f"{COMMITTED_MD.name} is out of date — regenerate and commit it:\n\n"
            f"{REGEN_CMD}\n\n{diff}")
