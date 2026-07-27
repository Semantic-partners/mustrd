"""Build the self-contained run viewer: one HTML file, driven by the run's RDF.

`mustrd/templates/viewer.html` is a complete vanilla-JS application — it carries
its own Turtle parser, so the *only* thing it needs is the run's triples. This
module produces those triples (coverage graph + per-test results graph + the
measured ontologies, merged) and inlines them into a copy of the template.

The result has no build step and no network dependency: attach it to a CI run,
open it from `file://`, or publish it on a static site. The same page also reads
data dropped onto it or fetched with `?ttl=`, so the template alone is a viewer
for any mustrd graph.
"""
import json
import logging
import os
from pathlib import Path

from rdflib import Graph

logger = logging.getLogger(__name__)

TEMPLATE = Path(__file__).parent / "templates" / "viewer.html"

# Placeholders in the template. Each is a *JSON string literal*, so substituting
# a json.dumps() value keeps the document valid whether or not it is filled in;
# an unfilled page falls back to its "drop a file" empty state.
_DATA_MARK = '"__MUSTRD_DATA__"'
_TITLE_MARK = "__MUSTRD_TITLE__"
_SRC_MARK = "__MUSTRD_SRC_BASE__"


def _json_for_html(value) -> str:
    """JSON-encode for embedding in a <script> block: escape `<` (and `&`) so the
    payload can never terminate the element early, whatever the Turtle contains."""
    return (json.dumps(value)
            .replace("<", "\\u003c")
            .replace(">", "\\u003e")
            .replace("&", "\\u0026"))


def merge_graphs(graphs) -> Graph:
    """One graph from many, keeping every prefix binding.

    rdflib's `+=` copies triples but not namespace bindings, and the viewer
    shortens IRIs purely from the `@prefix` lines it parses — so the bindings are
    what make the report legible. First binding for a prefix wins."""
    merged = Graph()
    bound = {}
    for g in graphs:
        if g is None:
            continue
        for prefix, ns in g.namespaces():
            if prefix and prefix not in bound:
                bound[prefix] = ns
                merged.bind(prefix, ns, override=False)
        merged += g
    return merged


def viewer_turtle(graphs) -> str:
    """The merged run graph as Turtle — the viewer's whole input."""
    return merge_graphs(graphs).serialize(format="turtle")


def github_src_base():
    """The `<server>/<repo>/blob/<sha>/` prefix for source links when running as a
    GitHub Action, so a published viewer links spec files to the repo web UI.
    None outside Actions, where cwd-relative links already resolve."""
    if os.environ.get("GITHUB_ACTIONS") != "true":
        return None
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com").rstrip("/")
    repo = os.environ.get("GITHUB_REPOSITORY")
    ref = os.environ.get("GITHUB_SHA") or os.environ.get("GITHUB_REF_NAME")
    if not (repo and ref):
        return None
    return f"{server}/{repo}/blob/{ref}/"


def build_viewer(graphs, title="mustrd run report", src_base=None) -> str:
    """The complete HTML document, with the run's Turtle inlined.

    `graphs` is any iterable of rdflib Graphs (None entries ignored) — typically
    the coverage graph, the results graph and the ontology graph. `src_base` is
    prefixed to spec/ontology source links; it defaults to the GitHub blob URL
    when running as an Action, and otherwise to relative paths."""
    html = TEMPLATE.read_text(encoding="utf-8")
    ttl = viewer_turtle(graphs)
    if src_base is None:
        src_base = github_src_base() or ""
    return (html
            .replace(_DATA_MARK, _json_for_html(ttl))
            .replace(_TITLE_MARK, _escape_text(title))
            .replace(_SRC_MARK, _escape_attr(src_base)))


def _escape_text(s) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _escape_attr(s) -> str:
    """For the JSON config block: keep it a valid JSON string."""
    return json.dumps(str(s))[1:-1].replace("<", "\\u003c")


def write_viewer(path, graphs, title="mustrd run report", src_base=None) -> None:
    parent = os.path.dirname(str(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    Path(path).write_text(build_viewer(graphs, title, src_base), encoding="utf-8")
    logger.info(f"Wrote run viewer to {path}")
