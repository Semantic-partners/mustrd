"""Tests for the self-contained run viewer (mustrd.viewer + templates/viewer.html).

Two halves:

- Python: the bundle really is self-contained (no external references), the run's
  Turtle survives the round trip into the page, and a hostile literal cannot
  break out of the <script> block.
- JavaScript: `test/viewer_smoke.mjs` boots the page's own app against a stub DOM
  and asserts the model it reads from the graph matches the Markdown report.
  Skipped when node is not on PATH.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from rdflib import Graph, Literal, Namespace, URIRef, RDF

from mustrd.cli import main
from mustrd.viewer import (
    TEMPLATE_FOLDER, build_viewer, merge_graphs, viewer_turtle,
)

EXAMPLE = Path("docs/examples/geography-example")
CONFIG = str(EXAMPLE / "mustrd-config.ttl")
EX = Namespace("http://example.org/x#")

# Matches src="…" / href="…" pointing at a remote host — a self-contained page
# must have none (the mustrd.org IRIs in the data are identifiers, not requests).
_REMOTE_REF = re.compile(r'(?:src|href)\s*=\s*["\'](?:https?:)?//', re.I)


@pytest.fixture(scope="module")
def viewer_html(tmp_path_factory):
    """A viewer built from the runnable geography example, via the CLI."""
    out = tmp_path_factory.mktemp("viewer") / "report.html"
    assert main(["report", "--config", CONFIG, "--viewer", str(out),
                 "--viewer-title", "Geography example"]) == 0
    return out


def _embedded_turtle_from(html):
    """The Turtle the page carries, read back the way the browser reads it."""
    m = re.search(r'<script id="mustrd-data" type="application/json">(.*?)</script>',
                  html, re.S)
    assert m, "the page has no embedded data block"
    return json.loads(m.group(1))


def _embedded_turtle(viewer_path_or_html):
    if isinstance(viewer_path_or_html, str):
        return _embedded_turtle_from(viewer_path_or_html)
    return _embedded_turtle_from(viewer_path_or_html.read_text(encoding="utf-8"))


def test_viewer_is_one_self_contained_file(viewer_html):
    html = viewer_html.read_text(encoding="utf-8")
    assert html.startswith("<!doctype html>")
    assert "Geography example" in html
    # No unsubstituted placeholders, and nothing to fetch: no CDN scripts, no
    # external stylesheets, no remote images.
    assert "__MUSTRD_DATA__" not in html
    assert "__MUSTRD_TITLE__" not in html
    assert "__MUSTRD_SRC_BASE__" not in html
    assert not _REMOTE_REF.search(html), _REMOTE_REF.search(html).group(0)


def test_embedded_turtle_is_the_run_graph(viewer_html):
    """The page's data is the real run graph — coverage, results and ontology."""
    g = Graph().parse(data=_embedded_turtle(viewer_html.read_text(encoding="utf-8")),
                      format="turtle")
    COV = Namespace("https://mustrd.org/coverage/")
    MUST = Namespace("https://mustrd.org/model/")
    CQ = Namespace("https://mustrd.org/competencyQuestion/")
    # coverage graph
    assert len(set(g.subjects(RDF.type, COV.TermCoverage))) == 11
    # results graph (--viewer implies it, without needing --results-rdf)
    assert len(set(g.subjects(RDF.type, COV.TestResult))) == 4
    # competency questions (--viewer implies the CQ overlay too)
    assert len(set(g.subjects(RDF.type, CQ.CompetencyQuestion))) == 4
    # the measured ontologies, merged in so the viewer can nest terms by subClassOf
    assert (URIRef("http://example.org/place#City"), None, None) in g
    assert len(set(g.subjects(RDF.type, MUST.TestSpec))) == 4


def test_viewer_matches_the_markdown_report(tmp_path):
    """One run, both outputs: the viewer's graph and the Markdown agree."""
    md = tmp_path / "report.md"
    html = tmp_path / "report.html"
    assert main(["report", "--config", CONFIG, "--term-coverage", "--cq",
                 "--md", str(md), "--viewer", str(html)]) == 0
    text = md.read_text(encoding="utf-8")
    assert "8/9 terms exercised by the tests = 89%" in text

    g = Graph().parse(data=_embedded_turtle(html.read_text(encoding="utf-8")),
                      format="turtle")
    DQV = Namespace("http://www.w3.org/ns/dqv#")
    COV = Namespace("https://mustrd.org/coverage/")
    ratios = {}
    for m in g.subjects(RDF.type, DQV.QualityMeasurement):
        ratios[str(g.value(m, DQV.isMeasurementOf))] = float(g.value(m, DQV.value))
    assert round(ratios[str(COV.termCoverageByTests)] * 100) == 89
    assert round(ratios[str(COV.termCoverageByCompetencyQuestions)] * 100) == 78


def test_spec_sources_are_embedded_by_default(viewer_html):
    """A path only resolves from the directory the run happened in, so the page
    carries the spec's Turtle, the SPARQL it ran, and the files it pulled in."""
    g = Graph().parse(data=_embedded_turtle(viewer_html.read_text(encoding="utf-8")),
                      format="turtle")
    COV = Namespace("https://mustrd.org/coverage/")
    sources = list(g.subjects(RDF.type, COV.SourceFile))
    # 4 spec files + the 4 queries they run + the 4 datasets they load.
    assert len(sources) == 12

    media = {str(g.value(s, COV.mediaType)) for s in sources}
    assert media == {"text/turtle", "application/sparql-query"}

    # Every Turtle node carries a path and the real file content.
    ttl = [s for s in sources if str(g.value(s, COV.mediaType)) == "text/turtle"]
    paths = sorted(str(g.value(s, COV.filePath)) for s in ttl)
    assert sum(p.endswith(".mustrd.ttl") for p in paths) == 4
    for s in ttl:
        path = str(g.value(s, COV.filePath))
        assert str(g.value(s, COV.fileText)) == Path(path).read_text(encoding="utf-8")

    # The SPARQL is the query as executed, so it has no path to resolve.
    sparql = [s for s in sources
              if str(g.value(s, COV.mediaType)) == "application/sparql-query"]
    assert all(g.value(s, COV.filePath) is None for s in sparql)
    assert any("SELECT" in str(g.value(s, COV.fileText)).upper() for s in sparql)


def test_transitively_referenced_files_are_embedded_and_linkable(viewer_html):
    """`must:file "mayor.ttl"` in a spec used to name a file the report did not
    have. The dataset is embedded now, and keeps the reference as the spec wrote
    it so the viewer can turn that literal into a link to this copy."""
    g = Graph().parse(data=_embedded_turtle(viewer_html.read_text(encoding="utf-8")),
                      format="turtle")
    COV = Namespace("https://mustrd.org/coverage/")

    by_reference = {str(g.value(s, COV.fileReference)): s
                    for s in g.subjects(COV.fileReference, None)}
    assert set(by_reference) == {"country.ttl", "division.ttl", "mayor.ttl", "region.ttl"}

    node = by_reference["mayor.ttl"]
    path = str(g.value(node, COV.filePath))
    # The reference resolved to a real dataset, recorded relative to the run.
    assert path == "docs/examples/geography-example/data/mayor.ttl"
    assert str(g.value(node, COV.fileText)) == Path(path).read_text(encoding="utf-8")
    # And it hangs off the spec that referenced it.
    specs = list(g.subjects(COV.embeddedSource, node))
    assert any("mayorOfRotterdam" in str(s) for s in specs)


def test_referenced_files_come_from_what_the_run_resolved():
    """The mapping is recorded where mustrd resolves a reference, so it cannot
    disagree with what was actually read."""
    from mustrd.spec_component import referenced_files
    from mustrd.sources_rdf import sources_graph
    COV = Namespace("https://mustrd.org/coverage/")

    assert main(["run", "--config", CONFIG]) == 0
    resolved = {ref for refs in referenced_files.values() for ref in refs}
    assert {"country.ttl", "mayor.ttl"} <= resolved

    # Passing the mapping in explicitly gives the same result as the recording.
    spec = next(iter(referenced_files))
    g = sources_graph([{"uri": spec, "queries": []}],
                      referenced={spec: referenced_files[spec]})
    assert [str(o) for o in g.objects(None, COV.fileReference)]


def test_no_viewer_sources_omits_them(tmp_path):
    html = tmp_path / "report.html"
    assert main(["report", "--config", CONFIG, "--viewer", str(html),
                 "--no-viewer-sources"]) == 0
    g = Graph().parse(data=_embedded_turtle(html.read_text(encoding="utf-8")),
                      format="turtle")
    COV = Namespace("https://mustrd.org/coverage/")
    assert not list(g.subjects(RDF.type, COV.SourceFile))
    # Still a complete report otherwise, just smaller.
    assert list(g.subjects(RDF.type, COV.TestResult))
    assert html.stat().st_size < viewer_size_with_sources(tmp_path)


def viewer_size_with_sources(tmp_path):
    out = tmp_path / "with-sources.html"
    main(["report", "--config", CONFIG, "--viewer", str(out)])
    return out.stat().st_size


def test_sources_graph_skips_unreadable_and_oversized_files():
    """Embedding is best-effort: a missing or absurdly large spec file must not
    fail the run."""
    from mustrd.sources_rdf import sources_graph
    COV = Namespace("https://mustrd.org/coverage/")
    specs = [
        {"uri": "http://example.org/a", "source_file": "does/not/exist.mustrd.ttl",
         "queries": ["SELECT * WHERE { ?s ?p ?o }"]},
        {"uri": None, "source_file": "ignored.ttl", "queries": ["SELECT 1"]},
        {"uri": "http://example.org/b", "source_file": "x.ttl", "queries": ["", None]},
    ]
    g = sources_graph(specs, read_file=lambda p: None)
    # No file nodes (nothing readable), but the query for the spec with a URI is
    # still embedded; the spec without a URI is skipped entirely.
    assert not list(g.subjects(COV.filePath, None))
    queries = list(g.subjects(RDF.type, COV.SourceFile))
    assert len(queries) == 1
    assert (URIRef("http://example.org/a"), COV.embeddedSource, queries[0]) in g


def test_viewer_reads_only_declared_vocabulary():
    """The viewer's model layer is a consumer of the coverage vocabulary, and it is
    JavaScript — so renaming or dropping a term cannot break it at import time the
    way it would a Python caller. This asserts every term the viewer reads is still
    declared, and fails pointing at the viewer when the vocabulary moves under it.

    (It cannot catch a term keeping its name but changing its *shape* — a boolean
    becoming an object property, say. viewer_smoke.mjs pins the rendering for that.)
    """
    model_js = (TEMPLATE_FOLDER / "viewer" / "model.js").read_text(encoding="utf-8")
    vocab = Graph()
    for ttl in ("coverage-ontology.ttl", "ontology.ttl", "cq-ontology.ttl"):
        vocab.parse(Path("mustrd/model") / ttl)

    namespaces = {
        "COV": "https://mustrd.org/coverage/",
        "MUST": "https://mustrd.org/model/",
        "CQNS": "https://mustrd.org/competencyQuestion/",
    }
    read = {(prefix, term)
            for prefix, base in namespaces.items()
            for term in re.findall(rf'{prefix} \+ "(\w+)"', model_js)}
    assert read, "found no vocabulary references in model.js — did the pattern change?"

    undeclared = sorted(f"{prefix}:{term}" for prefix, term in read
                        if (URIRef(namespaces[prefix] + term), None, None) not in vocab
                        and (None, None, URIRef(namespaces[prefix] + term)) not in vocab)
    assert not undeclared, (
        "mustrd/templates/viewer/model.js reads vocabulary that the ontologies no "
        f"longer declare: {', '.join(undeclared)}. Update the viewer to match."
    )


def test_merge_graphs_keeps_prefixes_and_triples():
    """The viewer shortens IRIs purely from the @prefix lines it parses, so the
    merge must carry bindings across (rdflib's += does not)."""
    a, b = Graph(), Graph()
    a.bind("ex", EX)
    a.add((EX.s, EX.p, Literal("a")))
    b.bind("other", Namespace("http://example.org/other#"))
    b.add((EX.s2, EX.p, Literal("b")))
    merged = merge_graphs([a, None, b])
    assert len(merged) == 2
    prefixes = {p for p, _ in merged.namespaces()}
    assert {"ex", "other"} <= prefixes
    assert "@prefix ex:" in viewer_turtle([a, b])


def test_hostile_literal_cannot_escape_the_script_block():
    """A spec name containing `</script>` must not terminate the data block."""
    g = Graph()
    g.bind("ex", EX)
    g.add((EX.s, EX.p, Literal("</script><script>alert(1)</script>")))
    html = build_viewer([g], title="<b>t</b> & more")
    body = re.search(r'<script id="mustrd-data" type="application/json">(.*?)</script>',
                     html, re.S).group(1)
    # The payload contains no raw '<', so the only </script> in it is the real one.
    assert "</script>" not in body
    assert "alert(1)" in json.loads(body)
    # And the title is escaped rather than injected as markup.
    assert "<b>t</b>" not in html
    assert "&lt;b&gt;t&lt;/b&gt; &amp; more" in html


def test_viewer_with_no_data_is_still_a_usable_viewer():
    """Rendered with no graphs, the page boots into its 'drop a file' empty state —
    it is a viewer for any mustrd graph, not just the run that produced it."""
    html = build_viewer([])
    assert html.startswith("<!doctype html>")
    assert "No run data loaded" in html
    assert not _REMOTE_REF.search(html)
    # Nothing to render, so the data block is an empty JSON string.
    assert _embedded_turtle_from(html).strip() == ""


def test_every_part_is_inlined():
    """The page is assembled from separate sources but must ship as one file."""
    html = build_viewer([])
    for name, marker in (
        ("viewer.css", "--font-mono:"),
        ("van.js", "let stateProto"),
        ("turtle.js", "function parseTurtle"),
        ("store.js", "function makeStore"),
        ("model.js", "function readTests"),
        ("ui.js", "van.add(document.body, Shell())"),
    ):
        assert (TEMPLATE_FOLDER / "viewer" / name).is_file(), name
        assert marker in html, f"{name} was not inlined"
    assert html.count("<script") == 3        # two JSON blocks and the app
    assert html.count("<style") == 1


@pytest.mark.parametrize("when,outcome,recorded", [
    ("setup", "passed", False),      # the call report that follows carries the outcome
    ("setup", "skipped", True),      # a skip never reaches the call phase
    ("setup", "failed", False),      # collection/fixture errors are not test outcomes
    ("call", "passed", True),
    ("call", "failed", True),
    ("teardown", "passed", False),
])
def test_plugin_records_the_outcomes_the_viewer_needs(when, outcome, recorded):
    """The results graph is three-valued, so the plugin has to record skips — which
    only ever appear as a *setup*-phase report."""
    from types import SimpleNamespace
    from mustrd.mustrdTestPlugin import MustrdTestPlugin

    class Item:                                  # pytest items are hashable dict keys
        session = SimpleNamespace(results={})

    plugin = MustrdTestPlugin(None, Path(CONFIG), None)
    item = Item()
    report = SimpleNamespace(when=when, outcome=outcome)

    gen = plugin.pytest_runtest_makereport(item, None)
    next(gen)                                    # run up to `outcome = yield`
    try:
        gen.send(SimpleNamespace(get_result=lambda: report))
    except StopIteration:
        pass

    assert (item in item.session.results) is recorded
    if recorded:
        assert item.session.results[item].outcome == outcome


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_viewer_app_renders_the_run(viewer_html, tmp_path):
    """Boot the page's own JavaScript (Turtle parser, model, all tabs) in node and
    check what it reads out of the graph."""
    expected = tmp_path / "expected.json"
    expected.write_text(json.dumps({
        "tests": 4, "passed": 4, "failed": 0, "skipped": 0,
        "terms": 11, "covered": 8, "pct": 89, "cqPct": 78,
        "ontologies": 2, "cqs": 4,
    }), encoding="utf-8")
    proc = subprocess.run(
        ["node", str(Path("test") / "viewer_smoke.mjs"), str(viewer_html), str(expected)],
        capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr or proc.stdout
    out = json.loads(proc.stdout)
    assert out["rendered"]["tests"] > 0 and out["rendered"]["coverage"] > 0
