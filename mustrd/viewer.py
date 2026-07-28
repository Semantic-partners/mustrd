"""Build the self-contained run viewer: one HTML file, driven by the run's RDF.

The page is assembled with Jinja from `mustrd/templates/viewer/`:

    viewer.html.jinja   the shell, which includes everything below
    viewer.css          the stylesheet
    van.js              vendored VanJS 1.6.1 (MIT)
    turtle.js           Turtle parser, term interning, JSON-LD reader
    store.js            the triple store and IRI shortening
    model.js            reading the run out of the graph
    ui.js               the VanJS views, loading and boot

Kept as separate sources so each part can be read, edited and tested on its own —
`test/viewer_smoke.mjs` runs the JavaScript straight from these files — and
inlined at render time so the *output* is still a single page with nothing to
fetch. This module supplies the triples (coverage graph + per-test results +
sources + the measured ontologies, merged).

The result has no build step and no network dependency: attach it to a CI run,
open it from `file://`, or publish it on a static site. It also reads data
dropped onto it or fetched with `?ttl=`, so a rendered page with no data inlined
is a viewer for any mustrd graph.
"""
import json
import logging
import os
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from rdflib import Graph

logger = logging.getLogger(__name__)

TEMPLATE_FOLDER = Path(__file__).parent / "templates"
TEMPLATE = "viewer/viewer.html.jinja"

# The parts the shell includes, in the order they are inlined. Named here so the
# packaging and the tests can check they are all present.
PARTS = ("viewer/viewer.css", "viewer/van.js", "viewer/turtle.js",
         "viewer/store.js", "viewer/model.js", "viewer/ui.js")


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


def _environment() -> Environment:
    # autoescape for the HTML shell (the title is the only text substituted into
    # markup); the two JSON payloads are pre-escaped by _json_for_html and marked
    # safe at the call site.
    return Environment(loader=FileSystemLoader(str(TEMPLATE_FOLDER)), autoescape=True)


class _Safe(str):
    """A string Jinja will not escape — `markupsafe.Markup` by another name,
    spelled out so the two JSON payloads are visibly the only unescaped
    substitutions in the document."""

    def __html__(self):
        return str(self)


def build_viewer(graphs, title="mustrd run report", src_base=None) -> str:
    """The complete HTML document, with the run's Turtle inlined.

    `graphs` is any iterable of rdflib Graphs (None entries ignored) — typically
    the coverage graph, the results graph, the embedded sources and the ontology
    graph. `src_base` is prefixed to source links that are not embedded in the
    page; it defaults to the GitHub blob URL when running as an Action, and
    otherwise to paths relative to the working directory."""
    if src_base is None:
        src_base = github_src_base() or ""
    return _environment().get_template(TEMPLATE).render(
        title=title,
        data_json=_Safe(_json_for_html(viewer_turtle(graphs))),
        config_json=_Safe(_json_for_html({"srcBase": str(src_base)})),
    )


def write_viewer(path, graphs, title="mustrd run report", src_base=None) -> None:
    parent = os.path.dirname(str(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    Path(path).write_text(build_viewer(graphs, title, src_base), encoding="utf-8")
    logger.info(f"Wrote run viewer to {path}")
