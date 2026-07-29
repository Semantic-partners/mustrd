#!/usr/bin/env python3
"""Build ontology publishing artifacts into docs/.

For each namespace, merges its ontology + shapes TTL files into a single graph
and emits serialisations under the slug that matches the namespace's URL path:

  docs/<slug>.ttl       (merged Turtle)
  docs/<slug>.rdf       (merged RDF/XML)
  docs/<slug>.jsonld    (merged JSON-LD)
  docs/<slug>.nt        (merged N-Triples)
  docs/<slug>.html      (browser view; served at the canonical /<slug>)

The original source files are also copied verbatim so they can still be fetched
individually:

  docs/<slug>/<original-filename>.ttl
"""

from __future__ import annotations

import html
import re
import shutil
import subprocess
from pathlib import Path

from rdflib import Graph, URIRef
from rdflib.namespace import OWL, RDF, RDFS, SH

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs"

# slug -> list of source TTL paths (relative to ROOT). The slug matches the
# path component of the namespace IRI so that IRI dereferencing resolves here.
ONTOLOGIES: list[tuple[str, list[str]]] = [
    ("model", [
        "mustrd/model/ontology.ttl",
        "mustrd/model/mustrdShapes.ttl",
    ]),
    ("triplestore", [
        "mustrd/model/triplestoreOntology.ttl",
        "mustrd/model/triplestoreshapes.ttl",
    ]),
    ("mustrdTest", [
        "mustrd/model/mustrdTestOntology.ttl",
        "mustrd/model/mustrdTestShapes.ttl",
    ]),
    ("coverage", [
        "mustrd/model/coverage-ontology.ttl",
    ]),
    ("competencyQuestion", [
        "mustrd/model/cq-ontology.ttl",
    ]),
]


def local_name(iri: str) -> str:
    for sep in ("#", "/"):
        if sep in iri:
            return iri.rsplit(sep, 1)[1] or iri
    return iri


def shorten(iri: str, prefixes: list[tuple[str, str]]) -> str:
    for pfx, ns in prefixes:
        if iri.startswith(ns):
            suffix = iri[len(ns):]
            return f"{pfx}:{suffix}" if pfx else f":{suffix}"
    return f"<{iri}>"


# --- schema diagram (graphviz) --------------------------------------------
# UML/ER-style class cards (data properties folded into attribute rows),
# object properties as labelled relations, subClassOf as hollow-triangle
# generalization. SP colour triad, clean sans, transparent background.
_DG = dict(
    hdr="#1f8fc4", hdr_t="#ffffff", border="#cbd0d8", ink="#2b2f36",
    muted="#9aa0ab", edge="#989fb0", edge_t="#5b6270", sub="#c2c7d0", font="Helvetica",
)


def _data_rows(g: Graph, cls: URIRef) -> list[tuple[str, str]]:
    rows = []
    for p in g.subjects(RDF.type, OWL.DatatypeProperty):
        if g.value(p, RDFS.domain) == cls:
            r = g.value(p, RDFS.range)
            rows.append((local_name(str(p)), local_name(str(r)) if r else ""))
    return sorted(rows)


def _card(g: Graph, cls: URIRef) -> str:
    e = html.escape
    body = ""
    for n, r in _data_rows(g, cls):
        rng = e(r) if r else "&#8212;"
        body += (
            f'<TR><TD ALIGN="LEFT"><FONT POINT-SIZE="11" COLOR="{_DG["ink"]}">{e(n)}</FONT></TD>'
            f'<TD ALIGN="LEFT"><FONT POINT-SIZE="10" COLOR="{_DG["muted"]}">{rng}</FONT></TD></TR>'
        )
    return (
        f'<<TABLE BORDER="1" COLOR="{_DG["border"]}" CELLBORDER="0" CELLSPACING="0" CELLPADDING="7">'
        f'<TR><TD COLSPAN="2" BGCOLOR="{_DG["hdr"]}" ALIGN="CENTER">'
        f'<FONT COLOR="{_DG["hdr_t"]}" POINT-SIZE="13"><B>{e(local_name(str(cls)))}</B></FONT></TD></TR>'
        f'{body}</TABLE>>'
    )


def schema_svg(g: Graph, slug: str) -> str:
    """Inline SVG for the ontology's object-property relation graph.

    Node set = classes that are the domain or range of an object property
    (leaf subclasses that only carry a subClassOf edge are left to a future
    hierarchy view, so this stays legible). Returns "" if graphviz is absent
    or the ontology has no object-property structure.
    """
    if not shutil.which("dot"):
        print("  (graphviz 'dot' not found — skipping diagram)")
        return ""
    e = html.escape
    objs = []
    for p in g.subjects(RDF.type, OWL.ObjectProperty):
        d, r = g.value(p, RDFS.domain), g.value(p, RDFS.range)
        if isinstance(d, URIRef) and isinstance(r, URIRef):
            objs.append((d, r, local_name(str(p))))
    nodeset = {c for d, r, _ in objs for c in (d, r)}
    if not nodeset:
        return ""
    subs = [(s, o) for s, o in g.subject_objects(RDFS.subClassOf)
            if s in nodeset and isinstance(o, URIRef) and o in nodeset]

    nid = lambda c: local_name(str(c))
    names = {nid(c) for c in nodeset}
    dot = [
        "digraph G {",
        f'  graph [bgcolor="transparent", rankdir=LR, nodesep=0.5, ranksep=1.0, pad=0.3, fontname="{_DG["font"]}"];',
        f'  node  [shape=plain, fontname="{_DG["font"]}"];',
        f'  edge  [fontname="{_DG["font"]}", fontsize=10, color="{_DG["edge"]}", '
        f'fontcolor="{_DG["edge_t"]}", penwidth=1.2, arrowsize=0.8];',
    ]
    for c in nodeset:
        dot.append(f'  "{nid(c)}" [label={_card(g, c)}];')
    for d, r, lbl in objs:
        dot.append(f'  "{nid(d)}" -> "{nid(r)}" [label="{e(lbl)}"];')
    for s, o in subs:
        dot.append(f'  "{nid(s)}" -> "{nid(o)}" [arrowhead="onormal", color="{_DG["sub"]}", arrowsize=1.0];')
    # TEMP (until the curation sidecar lands): pin canonical Given/When/Then order.
    gwt = [x for x in ("Given", "When", "Then") if x in names]
    if slug == "model" and len(gwt) > 1:
        dot.append("  { rank=same; " + "; ".join(f'"{x}"' for x in gwt) + "; }")
        dot.append("  " + " -> ".join(f'"{x}"' for x in gwt) + " [style=invis, weight=100];")
    dot.append("}")

    svg = subprocess.run(["dot", "-Tsvg"], input="\n".join(dot),
                         capture_output=True, text=True, check=True).stdout
    svg = svg[svg.index("<svg"):]                                   # drop xml/doctype preamble
    svg = re.sub(r'<svg width="[\d.]+pt" height="[\d.]+pt"', "<svg", svg, count=1)
    svg = svg.replace("<svg ", '<svg style="max-width:100%;height:auto" ', 1)  # responsive
    return svg


def render_html(g: Graph, slug: str) -> str:
    onto = next(g.subjects(RDF.type, OWL.Ontology), None)
    label = g.value(onto, RDFS.label) if onto else None
    comment = g.value(onto, RDFS.comment) if onto else None
    version = g.value(onto, OWL.versionInfo) if onto else None
    iri = str(onto) if onto else ""

    prefixes = sorted(((p, str(n)) for p, n in g.namespaces()), key=lambda x: -len(x[1]))

    def describe(subject: URIRef) -> dict:
        return {
            "iri": str(subject),
            "curie": shorten(str(subject), prefixes),
            "label": str(g.value(subject, RDFS.label) or local_name(str(subject))),
            "comment": str(g.value(subject, RDFS.comment) or ""),
            "local": local_name(str(subject)),
        }

    classes = sorted(
        (describe(s) for s in g.subjects(RDF.type, OWL.Class) if isinstance(s, URIRef)),
        key=lambda c: c["label"],
    )

    props: list[dict] = []
    for kind, klass in (("ObjectProperty", OWL.ObjectProperty), ("DatatypeProperty", OWL.DatatypeProperty)):
        for s in g.subjects(RDF.type, klass):
            if not isinstance(s, URIRef):
                continue
            d = describe(s)
            d["kind"] = kind
            dom = g.value(s, RDFS.domain)
            rng = g.value(s, RDFS.range)
            d["domain"] = shorten(str(dom), prefixes) if dom else "—"
            d["range"] = shorten(str(rng), prefixes) if rng else "—"
            props.append(d)
    props.sort(key=lambda p: p["label"])

    shapes = sorted(
        (describe(s) for s in g.subjects(RDF.type, SH.NodeShape) if isinstance(s, URIRef)),
        key=lambda s: s["label"],
    )

    e = html.escape

    def section(items: list[dict], kind: str) -> str:
        if not items:
            return "<p><em>None defined.</em></p>"
        if kind == "property":
            return "\n".join(
                f'<dt id="{e(i["local"])}">{e(i["label"])} '
                f'<span class="iri">{e(i["curie"])}</span></dt>'
                f'<dd>{e(i["comment"])}'
                f'<div class="meta">domain <code>{e(i["domain"])}</code> '
                f'&middot; range <code>{e(i["range"])}</code> '
                f'&middot; {e(i["kind"])}</div></dd>'
                for i in items
            )
        return "\n".join(
            f'<dt id="{e(i["local"])}">{e(i["label"])} '
            f'<span class="iri">{e(i["curie"])}</span></dt>'
            f'<dd>{e(i["comment"])}</dd>'
            for i in items
        )

    version_line = f" &middot; Version {e(str(version))}" if version else ""
    display_iri = iri or f"https://mustrd.org/{slug}/"

    diagram = schema_svg(g, slug)
    diagram_html = (
        f'<h2>Diagram</h2>\n<div class="diagram">{diagram}</div>\n'
        f'<p class="diagram-legend"><span class="sw"></span>&nbsp;class '
        f'&middot; &rarr; object property &middot; &#9655; subClassOf '
        f'&middot; rows are data properties</p>\n'
    ) if diagram else ""

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{e(str(label or slug))}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="icon" type="image/png" sizes="32x32" href="/favicon.png">
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<link rel="alternate" type="text/turtle" href="/{e(slug)}.ttl">
<link rel="alternate" type="application/rdf+xml" href="/{e(slug)}.rdf">
<link rel="alternate" type="application/ld+json" href="/{e(slug)}.jsonld">
<link rel="alternate" type="application/n-triples" href="/{e(slug)}.nt">
<style>
  body {{ font: 16px/1.5 system-ui, -apple-system, sans-serif; max-width: 52rem; margin: 0 auto; padding: 0 1rem 3rem; color: #222; }}
  h1 {{ font-size: 1.6rem; margin: 1.5rem 0 0.25rem; }}
  h2 {{ font-size: 1.15rem; margin-top: 2.5rem; border-bottom: 1px solid #ddd; padding-bottom: 0.25rem; }}
  dl {{ margin: 1rem 0; }}
  dt {{ font-weight: 600; margin-top: 1.25rem; }}
  dd {{ margin: 0.3rem 0 0 1rem; color: #333; }}
  code, .iri {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.9em; color: #555; }}
  .iri {{ color: #888; font-weight: normal; margin-left: 0.5em; }}
  .header-meta {{ color: #666; font-size: 0.9em; margin-top: 0.5rem; }}
  .serializations {{ margin: 1.5rem 0 2.5rem; }}
  .serializations a {{ display: inline-block; margin-right: 0.5rem; padding: 0.35rem 0.75rem; background: #f4f4f4; border-radius: 4px; text-decoration: none; color: #0645ad; font-family: ui-monospace, monospace; font-size: 0.85em; }}
  .serializations a:hover {{ background: #e8e8e8; }}
  .sources {{ margin: 1rem 0 1.5rem; font-size: 0.9em; color: #555; }}
  .sources a {{ color: #0645ad; text-decoration: none; }}
  .sources a:hover {{ text-decoration: underline; }}
  .meta {{ color: #777; font-size: 0.85em; margin-top: 0.3rem; }}
  p.home {{ margin-top: 2rem; font-size: 0.9em; }}
  p.home a {{ color: #0645ad; }}
  .diagram {{ margin: 1.25rem 0 0.5rem; overflow-x: auto; }}
  .diagram svg {{ max-width: 100%; height: auto; }}
  .diagram-legend {{ color: #777; font-size: 0.82em; margin: 0.25rem 0 0; }}
  .diagram-legend .sw {{ display: inline-block; width: 13px; height: 10px; border-radius: 2px; background: #1f8fc4; vertical-align: middle; }}
</style>
</head>
<body>
<p class="home"><a href="/">&larr; mustrd</a></p>
<h1>{e(str(label or slug))}</h1>
<p>{e(str(comment or ""))}</p>
<p class="header-meta">IRI <code>{e(display_iri)}</code>{version_line}</p>

<div class="serializations">
  Download merged graph:
  <a href="/{e(slug)}.ttl">Turtle</a>
  <a href="/{e(slug)}.rdf">RDF/XML</a>
  <a href="/{e(slug)}.jsonld">JSON-LD</a>
  <a href="/{e(slug)}.nt">N-Triples</a>
</div>

{diagram_html}
<h2>Classes</h2>
<dl>{section(classes, "entity")}</dl>

<h2>Properties</h2>
<dl>{section(props, "property")}</dl>

<h2>SHACL shapes</h2>
<dl>{section(shapes, "entity")}</dl>

</body>
</html>
"""


def build_ontology(slug: str, sources: list[str]) -> None:
    print(f"==> Building /{slug} from {sources}")
    g = Graph()
    for src in sources:
        g.parse(ROOT / src, format="turtle")

    base = OUT / slug
    OUT.mkdir(parents=True, exist_ok=True)

    for fmt, ext in (("turtle", "ttl"), ("pretty-xml", "rdf"), ("json-ld", "jsonld"), ("nt", "nt")):
        g.serialize(destination=f"{base}.{ext}", format=fmt)

    # Emit the browser view as <slug>.html. Pages' clean-URL handling serves it
    # at the canonical /<slug>, straight from the edge. (Content negotiation via
    # a Function is not possible for the bare /<slug>: the project serves its
    # not-found page for any path without a backing file *before* Functions run,
    # so the Function is never reached. A real file at /<slug> is served; RDF
    # stays available at /<slug>.ttl etc. and is advertised via <link rel=
    # "alternate"> in the page head.)
    Path(f"{base}.html").write_text(render_html(g, slug), encoding="utf-8")

    slug_dir = OUT / slug
    slug_dir.mkdir(parents=True, exist_ok=True)
    for src in sources:
        shutil.copy2(ROOT / src, slug_dir / Path(src).name)


def main() -> None:
    for slug, sources in ONTOLOGIES:
        build_ontology(slug, sources)
    print(f"Ontology artifacts written under {OUT}")


if __name__ == "__main__":
    main()
