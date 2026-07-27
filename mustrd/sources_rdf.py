"""Embed the sources a run read — spec Turtle and executed SPARQL — as RDF.

The rest of the run graph records *paths* (`must:specSourceFile`,
`cov:sourceFile`), which only resolve from the working directory the run happened
in. A report that travels — an emailed file, a CI artifact, a page on a static
site — needs the content, not a link into someone else's filesystem. So this
carries the text itself, as `cov:SourceFile` nodes hanging off each
`must:TestSpec`.

Kept out of the coverage/results graphs on purpose: the text literals are large
and say nothing about the ontology under test. Only the viewer consumes them.
"""
import logging
import os
from pathlib import Path

from rdflib import Graph, URIRef, Literal, RDF

from mustrd.coverage_rdf import COV, MUST, _relpath
from mustrd.coverage import _slug

logger = logging.getLogger(__name__)

TURTLE = "text/turtle"
SPARQL = "application/sparql-query"

# A spec file that is somehow enormous is a mistake, not something to inline into
# every report; skip it rather than producing a 50MB page.
MAX_BYTES = 512 * 1024


def _read(path):
    try:
        p = Path(path)
        if not p.is_file():
            logger.debug(f"Not embedding {path}: not a readable file")
            return None
        if p.stat().st_size > MAX_BYTES:
            logger.warning(f"Not embedding {path}: larger than {MAX_BYTES} bytes")
            return None
        return p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        logger.warning(f"Could not embed {path}: {e}")
        return None


def sources_graph(specs, read_file=_read) -> Graph:
    """The embedded-source graph for a run.

    `specs` is the same list of spec dicts the coverage computation consumes
    (see reporting.coverage_spec): each needs `uri`, and may have `source_file`
    and `queries`. Each distinct file is read once, however many specs share it —
    several specs commonly live in one .mustrd.ttl.
    """
    g = Graph()
    for p, ns in (("cov", COV), ("must", MUST)):
        g.bind(p, ns)

    file_nodes = {}                       # path -> node (or None if unreadable)
    for spec in specs:
        uri = spec.get("uri")
        if not uri:
            continue
        subject = URIRef(uri)

        src = spec.get("source_file")
        if src and str(src) != "unknown.mustrd.ttl":
            rel = _relpath(src)
            if rel not in file_nodes:
                text = read_file(src)
                node = None
                if text is not None:
                    node = URIRef(f"{COV}source/file/{_slug(rel)}")
                    g.add((node, RDF.type, COV.SourceFile))
                    g.add((node, COV.filePath, Literal(rel)))
                    g.add((node, COV.mediaType, Literal(_media_type(rel))))
                    g.add((node, COV.fileText, Literal(text)))
                file_nodes[rel] = node
            if file_nodes[rel] is not None:
                g.add((subject, COV.embeddedSource, file_nodes[rel]))

        # The SPARQL as executed — whatever its origin (inline in the spec, a .rq
        # file, or a query builder), so there is no path to resolve.
        for i, query in enumerate(spec.get("queries") or []):
            if not isinstance(query, str) or not query.strip():
                continue
            node = URIRef(f"{COV}source/query/{_slug(str(uri))}/{i}")
            g.add((node, RDF.type, COV.SourceFile))
            g.add((node, COV.mediaType, Literal(SPARQL)))
            g.add((node, COV.fileText, Literal(query)))
            g.add((subject, COV.embeddedSource, node))

    return g


def _media_type(path):
    return SPARQL if os.path.splitext(path)[1].lower() in (".rq", ".sparql") else TURTLE
