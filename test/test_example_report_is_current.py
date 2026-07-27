"""Golden test: the committed geography-example report is up to date.

`docs/examples/geography-example/report/term-coverage-example.{md,ttl}` are
generated artifacts checked into the repo (so they render on GitHub and document
the feature). If a change alters the report, the committed copies must be
regenerated and committed.

This regenerates both in the same environment they were committed from — from the
example directory, with the GitHub-Actions link/slug env removed so links are
relative and the run slug is 'local' — and fails (with the regenerate command)
if a committed copy is stale:

- the **.md** is compared byte-for-byte (deterministic jinja output);
- the **.ttl** is compared as an RDF **graph** (triple sets), so it's immune to
  Turtle serialisation-order differences across rdflib versions. The graph has no
  blank nodes, so equal triple sets means an identical graph.

Runs in CI (via `pytest test/`) and locally, so a stale report is caught before
merge.
"""
import difflib
from pathlib import Path

import pytest
from rdflib import Graph
from rdflib.compare import to_isomorphic, graph_diff

from mustrd.mustrdTestPlugin import MustrdTestPlugin

EXAMPLE = Path("docs/examples/geography-example").resolve()
COMMITTED_MD = Path("report/term-coverage-example.md")    # relative to EXAMPLE
COMMITTED_TTL = Path("report/term-coverage-example.ttl")

REGEN_CMD = (
    "(cd docs/examples/geography-example && \\\n"
    "   pytest . --mustrd --config=mustrd-config.ttl --term-coverage --cq \\\n"
    "          --md=report/term-coverage-example.md \\\n"
    "          --term-coverage-rdf=report/term-coverage-example.ttl)"
)


def _stale(name, extra=""):
    return (f"{name} is out of date — regenerate and commit it:\n\n{REGEN_CMD}\n\n{extra}")


def _md_diff(generated, committed):
    return "".join(difflib.unified_diff(
        committed.splitlines(True), generated.splitlines(True),
        fromfile="committed", tofile="regenerated"))


def _graph_diff(generated, committed):
    """Isomorphism check via rdflib.compare; "" when the graphs are equal, else a
    human-readable diff of the differing triples."""
    if to_isomorphic(generated) == to_isomorphic(committed):
        return ""
    _, only_committed, only_generated = graph_diff(to_isomorphic(committed),
                                                   to_isomorphic(generated))
    nm = committed.namespace_manager

    def fmt(g):
        return "\n".join("  " + " ".join(t[i].n3(nm) for i in range(3))
                         for t in sorted(g, key=str))
    parts = []
    if only_committed:
        parts.append("in committed but not regenerated:\n" + fmt(only_committed))
    if only_generated:
        parts.append("in regenerated but not committed:\n" + fmt(only_generated))
    return "\n\n".join(parts)


def test_committed_example_report_is_up_to_date(monkeypatch):
    # Reproduce the exact environment the committed files were generated in: from
    # the example dir, with the GitHub-Actions link/slug env removed. Write the
    # regenerated report into the same report/ directory (temp names) so its links
    # are relative to the same base as the committed copy.
    for var in ("GITHUB_ACTIONS", "GITHUB_SHA", "GITHUB_REPOSITORY",
                "GITHUB_SERVER_URL", "GITHUB_WORKSPACE"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.chdir(EXAMPLE)

    md = COMMITTED_MD.parent / "__golden_check__.md"
    ttl = COMMITTED_MD.parent / "__golden_check__.ttl"
    plugin = MustrdTestPlugin(str(md), Path("mustrd-config.ttl"), None,
                              term_coverage=True, cq=True, term_coverage_rdf=str(ttl))
    try:
        pytest.main([".", "-p", "no:cacheprovider"], plugins=[plugin])
        generated_md = md.read_text(encoding="utf-8")
        generated_graph = Graph().parse(ttl, format="turtle")
    finally:
        md.unlink(missing_ok=True)
        ttl.unlink(missing_ok=True)

    committed_md = COMMITTED_MD.read_text(encoding="utf-8")
    if generated_md != committed_md:
        pytest.fail(_stale(COMMITTED_MD.name, _md_diff(generated_md, committed_md)))

    committed_graph = Graph().parse(COMMITTED_TTL, format="turtle")
    diff = _graph_diff(generated_graph, committed_graph)
    if diff:
        pytest.fail(_stale(COMMITTED_TTL.name, diff))
