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
from mustrd.ontology import slug

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


def sources_graph(specs, read_file=_read, referenced=None, run_slug="local") -> Graph:
    """The embedded-source graph for a run.

    `specs` is the same list of spec dicts the coverage computation consumes
    (see reporting.coverage_spec): each needs `uri`, and may have `source_file`
    and `queries`. Each distinct file is read once, however many specs share it —
    several specs commonly live in one .mustrd.ttl.

    Nodes are minted under the run (`run/{run_slug}/source/...`). A file's content
    is the most run-contingent thing here — the same path holds different bytes next
    week — so a node shared across runs would end up asserting two contradictory
    cov:fileText values with nothing to tell them apart, which is exactly what
    merging two reports does. The spec IRI stays stable; only the observation of it
    is scoped.

    `referenced` is {spec IRI: {reference as written: resolved path}} — the files
    a spec pulls in transitively via must:file / must:fileurl (its given and then
    datasets, file-based queries). Defaults to what the run recorded while
    resolving them. The reference *as written* is kept alongside the path so the
    report can turn `must:file "mayor.ttl"` in a spec into a link to the copy of
    mayor.ttl it embedded.
    """
    if referenced is None:
        from mustrd.spec_component import referenced_files
        referenced = referenced_files

    g = Graph()
    for p, ns in (("cov", COV), ("must", MUST)):
        g.bind(p, ns)

    file_nodes = {}                       # path -> node (or None if unreadable)

    def embed(path, reference=None):
        """A cov:SourceFile for `path`, read once. `reference` is how the spec
        named it, when that differs from the path."""
        rel = _relpath(path)
        if rel not in file_nodes:
            text = read_file(path)
            node = None
            if text is not None:
                node = URIRef(f"{COV}run/{run_slug}/source/file/{slug(rel)}")
                g.add((node, RDF.type, COV.SourceFile))
                g.add((node, COV.filePath, Literal(rel)))
                g.add((node, COV.mediaType, Literal(_media_type(rel))))
                g.add((node, COV.fileText, Literal(text)))
            file_nodes[rel] = node
        node = file_nodes[rel]
        if node is not None and reference and str(reference) != rel:
            g.add((node, COV.fileReference, Literal(str(reference))))
        return node

    for spec in specs:
        uri = spec.get("uri")
        if not uri:
            continue
        subject = URIRef(uri)

        src = spec.get("source_file")
        if src and str(src) != "unknown.mustrd.ttl":
            node = embed(src)
            if node is not None:
                g.add((subject, COV.embeddedSource, node))

        # Whatever the spec pulled in: given/then datasets, file-based queries.
        for reference, path in sorted((referenced.get(str(uri)) or {}).items()):
            node = embed(path, reference)
            if node is not None:
                g.add((subject, COV.embeddedSource, node))

        # The SPARQL as executed — whatever its origin (inline in the spec, a .rq
        # file, or a query builder), so there is no path to resolve.
        for i, query in enumerate(spec.get("queries") or []):
            if not isinstance(query, str) or not query.strip():
                continue
            node = URIRef(f"{COV}run/{run_slug}/source/query/{slug(str(uri))}/{i}")
            g.add((node, RDF.type, COV.SourceFile))
            g.add((node, COV.mediaType, Literal(SPARQL)))
            g.add((node, COV.fileText, Literal(query)))
            g.add((subject, COV.embeddedSource, node))

    return g


_MEDIA_TYPES = {
    ".rq": SPARQL, ".sparql": SPARQL,
    ".ttl": TURTLE, ".n3": TURTLE, ".trig": "application/trig",
    ".nt": "application/n-triples", ".nq": "application/n-quads",
    ".jsonld": "application/ld+json", ".json": "application/json",
    ".csv": "text/csv", ".tsv": "text/tab-separated-values",
    ".rdf": "application/rdf+xml", ".xml": "application/rdf+xml",
    ".edn": "application/edn",
}


def _media_type(path):
    """Turtle is the default: an unrecognised extension here is far more likely to
    be a spec or dataset than anything else."""
    return _MEDIA_TYPES.get(os.path.splitext(path)[1].lower(), TURTLE)
