"""RDF / ontology introspection.

Pure read layer beneath coverage.py and cq.py: loading ontology files, listing
their owl:Ontology metadata, deriving declared class/property terms, extracting
the terms an ABox or a SPARQL query references, namespace helpers, and prefix
shortening. Knows nothing about specs, coverage, or competency questions.
"""
import logging
import os
import re
from pathlib import Path
from typing import Optional

from rdflib import Graph, URIRef, RDF, RDFS, OWL, XSD
from rdflib.namespace import DCTERMS, DC, SKOS
from rdflib.plugins.sparql import prepareQuery

log = logging.getLogger(__name__)


# Predicates checked, in order, for an ontology's human description.
DESCRIPTION_PREDICATES = (RDFS.comment, DCTERMS.description, DC.description,
                          SKOS.definition, RDFS.label)


# RDF serialisations recognised when scanning an ontology directory.
ONTOLOGY_SUFFIXES = {".ttl", ".trig", ".nt", ".nq", ".n3", ".jsonld", ".rdf", ".owl", ".xml"}


# Namespaces whose terms are infrastructure, not "the ontology under test".
WELL_KNOWN = (
    str(RDF), str(RDFS), str(OWL), str(XSD),
    "http://www.w3.org/2004/02/skos/core#",
    "http://www.w3.org/ns/shacl#",
    "https://mustrd.org/model/",
    "https://mustrd.org/competencyQuestion/",
    "http://purl.org/dc/elements/1.1/",
    "http://purl.org/dc/terms/",
    "http://www.w3.org/ns/prov#",
)


CLASS_TYPES = (OWL.Class, RDFS.Class)


PROPERTY_TYPES = frozenset((
    RDF.Property,
    OWL.ObjectProperty, OWL.DatatypeProperty, OWL.AnnotationProperty,
    OWL.OntologyProperty,
    OWL.FunctionalProperty, OWL.InverseFunctionalProperty,
    OWL.SymmetricProperty, OWL.TransitiveProperty,
))


# Property types that describe documentation/metadata rather than the domain
# vocabulary CQs are meant to exercise. A term declared *only* as one of these
# is treated as a schema term (excluded from the coverage %) when unused, rather
# than flagged as a gap. Mapped to the reason shown in the report.
METADATA_PROPERTY_TYPES = {
    OWL.AnnotationProperty: "annotation property",
    OWL.OntologyProperty: "ontology property",
}


_WELL_KNOWN_PREFIXES = ((str(OWL), "owl"), (str(RDFS), "rdfs"), (str(RDF), "rdf"))


def wk_qname(uri) -> str:
    """Render an rdf/rdfs/owl IRI with its conventional prefix (owl:Class …)."""
    s = str(uri)
    for ns, pfx in _WELL_KNOWN_PREFIXES:
        if s.startswith(ns):
            return f"{pfx}:{s[len(ns):]}"
    return s


def measured_namespaces(graph: Graph) -> frozenset:
    """The namespaces a graph declares itself to be — its owl:Ontology IRIs.

    Used to decide what counts as a domain term: "well-known" is relative to what
    you are measuring, not absolute. Pointing --ontology at mustrd's own model
    should measure must:, even though must: is infrastructure when the subject is
    somebody's domain vocabulary."""
    if graph is None:
        return frozenset()
    return frozenset(str(s) for s in graph.subjects(RDF.type, OWL.Ontology))


def is_domain_term(uri, measured=()) -> bool:
    """Whether `uri` is a term of the ontology under test rather than of the
    vocabulary it is written in.

    `measured` are namespaces being explicitly measured; a term in one of those
    counts even if its namespace is on the WELL_KNOWN list. Without that, a
    vocabulary on the list can never be the subject of a coverage run — which is
    what stopped mustrd measuring its own model."""
    if not isinstance(uri, URIRef):
        return False
    s = str(uri)
    if any(s.startswith(ns) for ns in measured):
        return True
    return not any(s.startswith(ns) for ns in WELL_KNOWN)


def namespace(iri: str) -> str:
    """The namespace of an IRI — up to and including its last '#' or '/'."""
    for sep in ("#", "/"):
        idx = iri.rfind(sep)
        if idx != -1:
            return iri[:idx + 1]
    return iri


def local_name(iri) -> str:
    """The local part of an IRI — everything after its last '#' or '/'."""
    s = str(iri)
    for sep in ("#", "/"):
        if sep in s:
            s = s.rsplit(sep, 1)[-1]
    return s or str(iri)


def slug(qname: str) -> str:
    """A URL-path-safe slug for a term's qname (e.g. place:City -> place.City),
    used to mint stable per-term IRIs in the RDF output."""
    return "".join(c if (c.isalnum() or c in "._-") else "_"
                   for c in qname.replace(":", "."))


def expand_ontology_files(paths) -> list:
    """Expand a list of file/directory paths into a sorted list of RDF files.

    Files are kept as-is; directories are scanned recursively for files with a
    recognised RDF suffix. Non-existent paths are skipped with a warning.
    """
    files = []
    for p in paths:
        p = Path(p)
        if p.is_dir():
            files.extend(sorted(f for f in p.rglob("*")
                                if f.is_file() and f.suffix.lower() in ONTOLOGY_SUFFIXES))
        elif p.is_file():
            files.append(p)
        else:
            log.warning(f"hasOntologyPath does not exist, skipping: {p}")
    # de-duplicate while preserving order
    seen, unique = set(), []
    for f in files:
        rp = f.resolve()
        if rp not in seen:
            seen.add(rp)
            unique.append(f)
    return unique


def ontology_report(paths, link_base=None, href=None) -> list:
    """Per-file summary of the ontologies under `paths`, for the report header.

    Each entry: {path, url, uri, description} — the file link (its href, see
    `_source_link`), the owl:Ontology IRI declared in that file (if any), and its
    description (rdfs:comment / dcterms:description / … ). A file with no
    owl:Ontology still appears (uri/description None); a file declaring several
    yields one row each. `href`, if given, is a callable path->url that overrides
    the default `link_base`-relative href (e.g. absolute GitHub URLs in CI).
    """
    rows = []
    for f in expand_ontology_files(paths):
        link = _source_link(f, link_base, href)
        g = Graph()
        try:
            g.parse(str(f))
        except Exception as e:
            log.warning(f"Could not parse ontology file {f}: {e}")
            rows.append({**link, "uri": None, "description": None})
            continue
        ontologies = sorted(str(s) for s in g.subjects(RDF.type, OWL.Ontology))
        if not ontologies:
            rows.append({**link, "uri": None, "version": None, "description": None})
        for uri in ontologies:
            version = g.value(subject=URIRef(uri), predicate=OWL.versionIRI)
            rows.append({**link, "uri": uri,
                         "version": str(version) if version is not None else None,
                         "description": _first_literal(g, URIRef(uri), DESCRIPTION_PREDICATES)})
    return rows


def _first_literal(graph: Graph, subject, predicates) -> Optional[str]:
    for p in predicates:
        val = graph.value(subject=subject, predicate=p)
        if val is not None:
            return str(val)
    return None


def load_ontology(paths) -> Optional[Graph]:
    """Parse every ontology file under `paths` (files or dirs) into one graph."""
    files = expand_ontology_files(paths)
    if not files:
        return None
    g = Graph()
    for f in files:
        try:
            g.parse(str(f))
        except Exception as e:
            log.warning(f"Could not parse ontology file {f}: {e}")
    return g


def term_ontology_index(paths) -> dict:
    """Map each declared term IRI -> the owl:Ontology IRI of the file that declares
    it (the first owl:Ontology in that file). The authoritative basis for linking a
    term to its ontology — based on where the term is actually declared, not a
    lexical namespace guess. Terms in a file with no owl:Ontology header are
    omitted (nothing authoritative to point at). First declaration wins."""
    index = {}
    for f in expand_ontology_files(paths):
        g = Graph()
        try:
            g.parse(str(f))
        except Exception as e:
            log.warning(f"Could not parse ontology file {f}: {e}")
            continue
        onts = sorted(str(s) for s in g.subjects(RDF.type, OWL.Ontology))
        if not onts:
            continue
        for t in declared_terms(g):
            index.setdefault(t, onts[0])
    return index


def declared_terms(graph: Graph, measured=None) -> dict:
    """Map each declared class/property IRI in the graph to 'class' or 'property'.

    Restricted to non-well-known namespaces (the ontology under test, not the
    RDF/RDFS/OWL/SKOS vocabulary it is written in) — except for namespaces the
    graph declares as its own, which is how a well-known vocabulary can still be
    the ontology under test. `measured` defaults to the graph's own owl:Ontology
    IRIs.
    """
    measured = measured_namespaces(graph) if measured is None else measured
    terms = {}
    for t in CLASS_TYPES:
        for s in graph.subjects(RDF.type, t):
            if is_domain_term(s, measured):
                terms.setdefault(str(s), "class")
    for t in PROPERTY_TYPES:
        for s in graph.subjects(RDF.type, t):
            if is_domain_term(s, measured):
                terms[str(s)] = "property"  # a property label wins over a class collision
    return terms


def metadata_terms(graph: Graph, measured=None) -> dict:
    """Domain terms declared *only* as annotation/ontology properties.

    Maps each such IRI to a reason label ("annotation property" /
    "ontology property"). These are documentation/metadata vocabulary, not the
    substantive classes and properties CQs exercise, so coverage reports an
    unused one as a schema term rather than a gap. A term also declared as a
    class or a substantive property is excluded — it is not "just metadata".
    """
    measured = measured_namespaces(graph) if measured is None else measured
    meta = {}
    for typ, label in METADATA_PROPERTY_TYPES.items():
        for s in graph.subjects(RDF.type, typ):
            if is_domain_term(s, measured):
                meta.setdefault(str(s), label)
    substantive = set()
    for typ in CLASS_TYPES:
        substantive |= {str(s) for s in graph.subjects(RDF.type, typ)}
    for typ in PROPERTY_TYPES - set(METADATA_PROPERTY_TYPES):
        substantive |= {str(s) for s in graph.subjects(RDF.type, typ)}
    return {iri: label for iri, label in meta.items() if iri not in substantive}


def _collect_uris(root) -> set:
    """Every URIRef reachable from a parsed-algebra node, walked iteratively.

    Descends dicts, sequences and objects' ``__dict__``; a seen-set on object
    identity guards against cycles.
    """
    found, seen, stack = set(), set(), [root]
    while stack:
        obj = stack.pop()
        if id(obj) in seen:
            continue
        seen.add(id(obj))
        if isinstance(obj, URIRef):
            found.add(str(obj))
        elif isinstance(obj, dict):
            stack.extend(obj.values())
        elif isinstance(obj, (list, tuple, set)):
            stack.extend(obj)
        elif hasattr(obj, "__dict__"):
            stack.extend(vars(obj).values())
    return found


def query_uris(query_text: str) -> set:
    """Every IRI referenced in a query's parsed algebra (ignores comments).

    Handles SELECT/CONSTRUCT/ASK/DESCRIBE and, as a fallback, SPARQL Update.
    """
    try:
        algebra = prepareQuery(query_text).algebra
    except Exception as query_exc:
        try:
            from rdflib.plugins.sparql.parser import parseUpdate
            from rdflib.plugins.sparql.algebra import translateUpdate
            algebra = translateUpdate(parseUpdate(query_text))
        except Exception as update_exc:
            log.debug("query_uris: could not parse as query (%s) nor update (%s); "
                      "extracting no query terms from: %s",
                      query_exc, update_exc, query_text)
            return set()
    return _collect_uris(algebra)


def abox_terms(graph: Graph) -> set:
    """Terms USED by instance data: rdf:type objects + asserted predicates."""
    used = {str(o) for o in graph.objects(None, RDF.type) if isinstance(o, URIRef)}
    used |= {str(p) for p in set(graph.predicates()) if isinstance(p, URIRef)}
    return used


_PREFIX_RE = re.compile(r"PREFIX\s+([A-Za-z][\w.\-]*)\s*:\s*<([^>]*)>", re.IGNORECASE)


def shortener(graphs, query_texts=()):
    """Build a prefix map -> function turning an IRI into a qname.

    Sources both the given graphs and the `PREFIX` declarations in the query
    text. mustrd's given graph often loses author prefixes (rdflib
    auto-generates `ns1`, `ns2`, ... on collisions), whereas the SPARQL
    `PREFIX ex: <...>` lines are author-chosen and clean. Per namespace we pick
    the cleanest prefix: prefer one not ending in a digit, then the shortest.
    """
    candidates = {}  # namespace -> set of prefixes
    for g in graphs:
        for prefix, ns in g.namespaces():
            if prefix:  # skip the default (empty) prefix
                candidates.setdefault(str(ns), set()).add(prefix)
    for text in query_texts:
        for prefix, ns in _PREFIX_RE.findall(text or ""):
            candidates.setdefault(ns, set()).add(prefix)

    def best(prefixes):
        return sorted(prefixes, key=lambda p: (p[-1].isdigit(), len(p), p))[0]

    ns_to_prefix = {ns: best(pfx) for ns, pfx in candidates.items()}
    # longest namespace first, so the most specific binding wins
    ordered = sorted(ns_to_prefix.items(), key=lambda kv: len(kv[0]), reverse=True)

    def short(uri: str) -> str:
        for ns, prefix in ordered:
            if uri.startswith(ns):
                return f"{prefix}:{uri[len(ns):]}"
        return uri

    return short


def _source_link(p, link_base=None, href=None) -> dict:
    """Display label + a link href.

    When `href` (a path->url callable) is given it decides the url — used to emit
    absolute GitHub URLs in CI. Otherwise the url is RELATIVE to `link_base`
    (Markdown previewers like VS Code block absolute `file://` links, so a
    relative href resolves against the report's own location): the report file's
    directory for an `--md` file, or the cwd for terminal output. The label stays
    relative to the cwd for readability.
    """
    p = Path(p)
    try:
        label = os.path.relpath(p)
    except ValueError:  # e.g. different drive on Windows
        label = str(p)
    if href is not None:
        url = href(p)
    else:
        base = Path(link_base) if link_base is not None else Path.cwd()
        try:
            url = os.path.relpath(p, base)
        except ValueError:
            url = str(p)
    # forward slashes so paths/links are OS-independent (Markdown/URLs never use "\")
    return {"path": label.replace(os.sep, "/"),
            "url": url.replace(os.sep, "/") if url else url}
