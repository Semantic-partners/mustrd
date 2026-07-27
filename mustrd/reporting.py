"""Pure reporting library: turn collected spec results (+ competency-question
defs) into the canonical RDF graph and the Markdown report.

This is the shared core behind BOTH the pytest plugin (mustrdTestPlugin.py) and
the `mustrd` CLI (cli.py), so the two produce identical output. It has no pytest
dependency — callers hand it plain data (spec dicts, CQ defs, a `ReportOptions`)
and it computes coverage/CQ, builds the graph, renders Markdown, and writes the
requested artifacts.

The design intent (see coverage_render.py) holds here: the RDF graph is the
canonical run output and the Markdown report is rendered *from it*.
"""
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from rdflib import Graph, RDF

from mustrd.TestResult import (
    render_cq_table, render_term_coverage, render_ontologies,
    render_duplicate_cqs, render_per_cq, render_cq_gaps, render_tbox_in_data,
    ResultList, get_result_list,
)
from mustrd.coverage import compute_coverage, apply_term_links
from mustrd.ontology import load_ontology, ontology_report, local_name
from mustrd.cq import cq_facts
from mustrd.coverage_rdf import coverage_graph, cq_graph
from mustrd.coverage_render import coverage_context, read_ontologies
from mustrd.cq_render import cq_report
from mustrd.namespace import CQ

logger = logging.getLogger(__name__)


@dataclass
class ReportOptions:
    """What to compute and where to write it. The plugin fills this from pytest
    options; the CLI fills it from argparse."""
    md_path: str = None
    term_coverage: bool = False
    cq: bool = False
    term_coverage_rdf: str = None
    term_coverage_jsonld: str = None    # coverage graph as JSON-LD (for the viewer)
    results_rdf: str = None             # per-test results graph, Turtle
    results_jsonld: str = None          # per-test results graph, JSON-LD (viewer)
    viewer: str = None                  # self-contained HTML viewer (data inlined)
    viewer_title: str = "mustrd run report"
    viewer_src_base: str = None         # prefix for the viewer's source-file links
    viewer_sources: bool = True         # inline each spec's TTL + SPARQL in the page
    term_links: str = "off"
    ontology_paths: tuple = field(default_factory=tuple)


def _ensure_parent(path):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def wants_coverage(opts: ReportOptions) -> bool:
    """--term-coverage-rdf and --viewer also need coverage computed (and an
    ontology): both are consumers of the coverage graph, not just the terminal."""
    return (opts.term_coverage or bool(opts.term_coverage_rdf) or bool(opts.viewer)) \
        and bool(opts.ontology_paths)


def wants_cq(opts: ReportOptions) -> bool:
    """Whether to put the competency-question overlay in the graph. The viewer has
    a CQ tab, so it wants the overlay too — but *only* the graph: the Markdown
    report's CQ section stays gated on --cq alone."""
    return opts.cq or bool(opts.viewer)


# ---------------------------------------------------------------------------
# Link helpers (source-file path -> report href). Pure; env-aware.
# ---------------------------------------------------------------------------
def _github_blob_prefix():
    """In GitHub Actions, the '<server>/<repo>/blob/<sha>/' prefix for linking a
    repo file on the GitHub web UI; None when not running as an Action."""
    if os.environ.get("GITHUB_ACTIONS") != "true":
        return None
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com").rstrip("/")
    repo = os.environ.get("GITHUB_REPOSITORY")
    ref = os.environ.get("GITHUB_SHA") or os.environ.get("GITHUB_REF_NAME")
    if not (repo and ref):
        return None
    return f"{server}/{repo}/blob/{ref}/"


def _link_href(link_base):
    """Return a function mapping a source-file path to its report href.

    In a GitHub Actions run the job summary is rendered on the Actions page, where
    report-relative links don't resolve — so links become absolute URLs into the
    repo on the GitHub web UI (path taken relative to GITHUB_WORKSPACE). Otherwise
    they stay relative to `link_base` (the report dir for --md, the cwd for
    terminal output) so a Markdown previewer resolves them."""
    prefix = _github_blob_prefix()
    root = os.environ.get("GITHUB_WORKSPACE") or os.getcwd()

    def href(src):
        if not src or str(src) == "unknown.mustrd.ttl":
            return None
        src = str(src)
        if prefix:
            try:
                return prefix + os.path.relpath(src, root).replace(os.sep, "/")
            except ValueError:
                return None
        try:
            # forward slashes so links are portable (Markdown/URLs never use "\\")
            return os.path.relpath(src, link_base or ".").replace(os.sep, "/")
        except ValueError:
            return src.replace(os.sep, "/")
    return href


def _link_report_refs(coverage, href):
    """Set the `link` (the href to the referencing spec file) on every spec
    reference in the report — undeclared-term refs, per-term cover refs, CQ-gap
    refs, duplicate-CQ nodes, and the TBox-in-data entries."""
    if not coverage:
        return
    ref_lists = [t.get("refs", []) for t in coverage.get("undeclared", [])]
    ref_lists += [t.get("cover_refs", []) for t in coverage.get("terms", [])]
    ref_lists += [t.get("non_cq_refs", []) for t in coverage.get("cq_gaps", [])]
    ref_lists += [d.get("cqs", []) for d in coverage.get("duplicate_cqs", [])]
    # TBox-in-data entries carry their own source_file/link directly.
    ref_lists += [coverage.get("tbox_in_data", [])]
    for refs in ref_lists:
        for ref in refs:
            ref["link"] = href(ref.get("source_file"))


# ---------------------------------------------------------------------------
# Spec-dict projection (shared input shape for coverage).
# ---------------------------------------------------------------------------
def coverage_spec(spec, outcome, test_name):
    """Project a mustrd Specification + its outcome string into the plain dict
    compute_coverage consumes. `outcome` is 'passed' / 'failed' / 'skipped'."""
    when = getattr(spec, 'when', None)
    # `when` may be a single WhenSpec or a list of them.
    when_list = when if isinstance(when, list) else ([when] if when is not None else [])
    queries = [w.value for w in when_list if isinstance(getattr(w, 'value', None), str)]
    uri = getattr(spec, 'spec_uri', None)
    return {
        "name": getattr(spec, 'spec_file_name', test_name),
        "uri": str(uri) if uri is not None else None,
        "passed": outcome == "passed",
        "given": getattr(spec, 'given', None),
        "queries": queries,
        "source_file": getattr(spec, 'spec_source_file', None),
    }


# ---------------------------------------------------------------------------
# Competency questions.
# ---------------------------------------------------------------------------
def collect_cq_defs(spec_paths, spec_by_uri):
    """Find every cq:CompetencyQuestion node under the given spec paths and
    resolve its cq:cqSpec links. A CQ may live in any *.mustrd.ttl under a
    config's hasSpecPath, and may point at 0..n specs (or none). Unresolvable
    cqSpec targets are kept in `missing_specs` so the table can flag them.
    Returns [{id, name, question, questions, source_file, specs, missing_specs}]."""
    defs, seen = [], set()
    for sp in spec_paths:
        for ttl in sorted(Path(sp).glob("**/*.mustrd.ttl")):
            g = Graph()
            try:
                g.parse(ttl)
            except Exception:
                continue
            for cq in g.subjects(RDF.type, CQ.CompetencyQuestion):
                cid = str(cq)
                if cid in seen:
                    continue
                seen.add(cid)
                questions = [str(o) for o in g.objects(cq, CQ.question)]
                specs, missing = [], []
                for u in (str(o) for o in g.objects(cq, CQ.cqSpec)):
                    (specs.append(spec_by_uri[u]) if u in spec_by_uri
                     else missing.append(u))
                defs.append({
                    "id": cid, "name": local_name(cid),
                    "question": questions[0] if questions else None,
                    "questions": questions, "source_file": str(ttl),
                    "specs": specs, "missing_specs": missing,
                })
    return sorted(defs, key=lambda d: (d.get("question") or "", d["name"]))


# ---------------------------------------------------------------------------
# Run identity + graph building.
# ---------------------------------------------------------------------------
def run_ident():
    """run_slug / commit / mustrd_version for a graph, from the CI env."""
    sha = os.environ.get("GITHUB_SHA")
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com").rstrip("/")
    repo = os.environ.get("GITHUB_REPOSITORY")
    try:
        from importlib.metadata import version
        mustrd_version = version("mustrd")
    except Exception:
        mustrd_version = None
    return {"run_slug": sha or "local",
            "commit": f"{server}/{repo}/commit/{sha}" if (sha and repo) else None,
            "mustrd_version": mustrd_version}


def _coverage_graph(coverage, ontology_paths):
    """Build the canonical coverage RDF graph."""
    ontologies = [{"uri": r["uri"], "version": r.get("version"),
                   "description": r.get("description"), "path": r.get("path")}
                  for r in ontology_report(ontology_paths) if r.get("uri")]
    return coverage_graph(coverage, ontologies, **run_ident())


def compute(all_specs, cq_defs, ontology_paths, report_cq):
    """Compute coverage and build its canonical RDF graph. Returns
    (coverage_dict, ontology_graph, graph); (None, None, None) on failure or
    when nothing is declared."""
    try:
        ontology_graph = load_ontology(ontology_paths)
        coverage = compute_coverage(all_specs, ontology=ontology_graph,
                                    cq_defs=cq_defs if report_cq else None)
        if coverage is None:
            return None, None, None
        return coverage, ontology_graph, _coverage_graph(coverage, ontology_paths)
    except Exception as e:
        logger.warning(f"Could not compute ontology term coverage: {e}")
        return None, None, None


def build_report_data(all_specs, cq_defs, opts: ReportOptions,
                      report_coverage: bool, report_cq: bool):
    """The canonical RDF outputs of a run: (coverage, ontology_graph, graph).

    With an ontology it's the full coverage graph (with a CQ overlay when --cq);
    with `--cq` alone it's a CQ-only graph (no measurements). compute() returns
    None coverage if nothing is declared."""
    coverage, ontology_graph, graph = \
        compute(all_specs, cq_defs, opts.ontology_paths, report_cq) if report_coverage \
        else (None, None, None)
    if graph is None and report_cq:              # --cq with no ontology
        graph = cq_graph(cq_facts(cq_defs), **run_ident())
    return coverage, ontology_graph, graph


# ---------------------------------------------------------------------------
# Markdown rendering.
# ---------------------------------------------------------------------------
def render_result_list(test_results, is_mustrd):
    """The pre-existing (master) --md report: a ResultList of every test."""
    result_list = ResultList(
        None,
        get_result_list(
            test_results,
            lambda result: result.type,
            lambda result: is_mustrd and result.test_name.split("@")[1],
        ),
        False,
    )
    return result_list.render()


def render_markdown(graph, ontology_graph, coverage, link_base, opts: ReportOptions):
    """Assemble the report, rendered entirely FROM the RDF graph (+ the
    ontology for the subClassOf tree). Two H2 sub-reports under a top title:

      # Ontologies Report
      ## Coverage Report              (when an ontology was checked)
      ## Competency Questions Report  (--cq)
    """
    parts = []
    href = _link_href(link_base)
    if coverage is not None and graph is not None and ontology_graph is not None:
        ctx = coverage_context(graph, ontology_graph)
        _link_report_refs(ctx, href)
        apply_term_links(ctx, opts.term_links, opts.ontology_paths, link_base)
        parts.append("# Ontologies Report")
        parts.append("## Coverage Report")
        ontologies = read_ontologies(graph)
        for o in ontologies:
            o["url"] = href(o["path"])
        if ontologies:
            parts.append(render_ontologies(ontologies))
        parts.append(render_term_coverage(ctx))
        if ctx.get("tbox_in_data"):
            parts.append(render_tbox_in_data(ctx["tbox_in_data"]))
    if opts.cq and graph is not None:
        cqr = cq_report(graph, ontology_graph, href)
        apply_term_links(cqr, opts.term_links, opts.ontology_paths, link_base)
        parts.append("## Competency Questions Report" if coverage is not None
                     else "# Competency Questions Report")
        parts.append(render_cq_table(cqr["per_cq"], show_coverage=cqr["has_ontology"]))
        if cqr["duplicate_cqs"]:
            parts.append(render_duplicate_cqs(cqr["duplicate_cqs"]))
        if cqr["has_ontology"]:
            parts.append(render_cq_gaps(cqr["cq_gaps"]))
        if cqr["per_cq"]:
            parts.append(render_per_cq(cqr["per_cq"], unchecked=not cqr["has_ontology"]))
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Orchestration + emit.
# ---------------------------------------------------------------------------
def produce_report(all_specs, cq_defs, test_results, last_is_mustrd,
                   opts: ReportOptions, terminal_writer=None, run_results=None):
    """Compute the run's report data and write the requested artifacts:

      - the --md Markdown file (assembled report with --term-coverage/--cq,
        otherwise the ResultList of every test),
      - the coverage graph as Turtle (--term-coverage-rdf) and/or JSON-LD
        (--term-coverage-jsonld, for the standalone viewer),
      - the per-test results graph (`run_results`) as Turtle and/or JSON-LD,
      - the self-contained HTML viewer (--viewer): all of those graphs merged and
        inlined into a single page that renders them in the browser,
      - the terminal body (only for the human-facing flags) via `terminal_writer`
        (a callback taking the report body; None to skip).

    Returns the (coverage, ontology_graph, graph) it built, for callers that want
    to emit further serializations.
    """
    report_coverage = wants_coverage(opts)
    report_cq = wants_cq(opts)

    coverage, ontology_graph, graph = build_report_data(
        all_specs, cq_defs, opts, report_coverage, report_cq)

    # Markdown report.
    if opts.md_path:
        if report_coverage or report_cq:
            md = render_markdown(graph, ontology_graph, coverage,
                                 os.path.dirname(opts.md_path) or ".", opts)
        else:
            md = render_result_list(test_results, last_is_mustrd)
        _ensure_parent(opts.md_path)
        with open(opts.md_path, "w", encoding="utf-8") as file:
            file.write(md)

    # Coverage graph — Turtle (--term-coverage-rdf) for a knowledge graph, and/or
    # JSON-LD (--term-coverage-jsonld) for the browser viewer.
    if opts.term_coverage_rdf and graph is not None:
        _ensure_parent(opts.term_coverage_rdf)
        graph.serialize(destination=opts.term_coverage_rdf, format="turtle")
    if opts.term_coverage_jsonld and graph is not None:
        _ensure_parent(opts.term_coverage_jsonld)
        graph.serialize(destination=opts.term_coverage_jsonld, format="json-ld")

    # Per-test results graph (every test, three-valued, with timing) — the data
    # behind the viewer's Playwright-style tree.
    results_g = None
    if run_results and (opts.results_rdf or opts.results_jsonld or opts.viewer):
        from mustrd.results_rdf import results_graph
        results_g = results_graph(run_results, **run_ident())
        if opts.results_rdf:
            _ensure_parent(opts.results_rdf)
            results_g.serialize(destination=opts.results_rdf, format="turtle")
        if opts.results_jsonld:
            _ensure_parent(opts.results_jsonld)
            results_g.serialize(destination=opts.results_jsonld, format="json-ld")

    # The self-contained HTML viewer: the same graphs, inlined into one page —
    # plus, by default, the text of each spec and the SPARQL it ran, so the report
    # is readable without access to the files it was generated from.
    if opts.viewer:
        from mustrd.viewer import write_viewer
        sources_g = None
        if opts.viewer_sources:
            from mustrd.sources_rdf import sources_graph
            sources_g = sources_graph(all_specs)
        write_viewer(opts.viewer, [graph, results_g, ontology_graph, sources_g],
                     title=opts.viewer_title, src_base=opts.viewer_src_base)

    # To the terminal — only for the human-facing flags (not RDF/viewer-only runs).
    if (opts.term_coverage or opts.cq) and terminal_writer is not None:
        body = render_markdown(graph, ontology_graph, coverage, os.getcwd(), opts)
        terminal_writer(body)

    return coverage, ontology_graph, graph
