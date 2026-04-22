#!/usr/bin/env python3
"""Build ontology publishing artifacts into docs/.

For each namespace, merges its ontology + shapes TTL files into a single graph
and emits serialisations under the slug that matches the namespace's URL path:

  docs/<slug>.ttl       (merged Turtle)
  docs/<slug>.rdf       (merged RDF/XML)
  docs/<slug>.jsonld    (merged JSON-LD)
  docs/<slug>.nt        (merged N-Triples)
  docs/<slug>-doc.html  (browser view)

The original source files are also copied verbatim so they can still be fetched
individually:

  docs/<slug>/<original-filename>.ttl
"""

from __future__ import annotations

import html
import shutil
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

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{e(str(label or slug))}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
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

    # Emit HTML under a -doc suffix so Pages' clean-URL behavior doesn't serve
    # it for the canonical /<slug> (which must reach the Function for
    # content negotiation).
    Path(f"{base}-doc.html").write_text(render_html(g, slug), encoding="utf-8")

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
