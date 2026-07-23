"""Ontology term coverage over mustrd tests.

See docs/ontology-term-coverage.md for the design. In short: given the specs
mustrd already parsed, work out which ontology terms the *passing* tests actually
exercise — in their input data (ABox) or their SPARQL — and which declared terms
nothing touches. The competency-question overlay (per-CQ breakdown, CQ coverage
%, duplicate detection) lives in the sibling module `mustrd.cq`, which reuses the
term helpers here.

A term is COVERED if a passing spec populates it in its input data (as an object
of rdf:type, or as an asserted predicate); a term only named in a SPARQL query
but never instantiated is *query-only* — reported as a gap, not coverage.

TBox declarations do NOT count as usage — detecting usage via rdf:type objects
and asserted predicates structurally ignores owl:Class / rdfs:subClassOf /
rdfs:domain axioms, so loading the ontology into a `given` never inflates the
score. The set of DECLARED terms is derived from those same given graphs (the
subjects typed as a class or property), restricted to non-well-known
namespaces so vocabulary terms like rdfs:label are not mistaken for the
ontology under test.
"""
import logging
import os
import re
from pathlib import Path
from typing import List, Optional

from rdflib import Graph, URIRef, RDF, RDFS, OWL, XSD
from rdflib.namespace import DCTERMS, DC, SKOS
from rdflib.plugins.sparql import prepareQuery

# Predicates checked, in order, for an ontology's human description.
DESCRIPTION_PREDICATES = (RDFS.comment, DCTERMS.description, DC.description,
                          SKOS.definition, RDFS.label)

log = logging.getLogger(__name__)

# RDF serialisations recognised when scanning an ontology directory.
ONTOLOGY_SUFFIXES = {".ttl", ".trig", ".nt", ".nq", ".n3", ".jsonld", ".rdf", ".owl", ".xml"}

# Namespaces whose terms are infrastructure, not "the ontology under test".
WELL_KNOWN = (
    str(RDF), str(RDFS), str(OWL), str(XSD),
    "http://www.w3.org/2004/02/skos/core#",
    "http://www.w3.org/ns/shacl#",
    "https://mustrd.org/model/",
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

CLASS_TYPES = (OWL.Class, RDFS.Class)

# rdf:type objects and predicates that make a triple a TBox (schema) axiom. When
# these appear in a test's `given`, the fixture is defining ontology structure —
# which belongs in the ontology, not the test data — so the report hints they be
# moved. Type set is derived from the property types above so it can't drift.
TBOX_TYPES = CLASS_TYPES + tuple(PROPERTY_TYPES)
TBOX_PREDICATES = (RDFS.subClassOf, RDFS.subPropertyOf, RDFS.domain, RDFS.range)

_WELL_KNOWN_PREFIXES = ((str(OWL), "owl"), (str(RDFS), "rdfs"), (str(RDF), "rdf"))


def _wk_qname(uri) -> str:
    """Render an rdf/rdfs/owl IRI with its conventional prefix (owl:Class …)."""
    s = str(uri)
    for ns, pfx in _WELL_KNOWN_PREFIXES:
        if s.startswith(ns):
            return f"{pfx}:{s[len(ns):]}"
    return s


def _is_domain_term(uri) -> bool:
    return isinstance(uri, URIRef) and not any(str(uri).startswith(ns) for ns in WELL_KNOWN)


def _namespace(iri: str) -> str:
    """The namespace of an IRI — up to and including its last '#' or '/'."""
    for sep in ("#", "/"):
        idx = iri.rfind(sep)
        if idx != -1:
            return iri[:idx + 1]
    return iri


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


def ontology_report(paths, link_base=None) -> list:
    """Per-file summary of the ontologies under `paths`, for the report header.

    Each entry: {path, url, uri, description} — the file link (href relative to
    `link_base`, see `_source_link`), the owl:Ontology IRI declared in that file
    (if any), and its description (rdfs:comment / dcterms:description / … ). A
    file with no owl:Ontology still appears (uri/description None); a file
    declaring several yields one row each.
    """
    rows = []
    for f in expand_ontology_files(paths):
        link = _source_link(f, link_base)
        g = Graph()
        try:
            g.parse(str(f))
        except Exception as e:
            log.warning(f"Could not parse ontology file {f}: {e}")
            rows.append({**link, "uri": None, "description": None})
            continue
        ontologies = sorted(str(s) for s in g.subjects(RDF.type, OWL.Ontology))
        if not ontologies:
            rows.append({**link, "uri": None, "description": None})
        for uri in ontologies:
            rows.append({**link, "uri": uri,
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


def declared_terms(graph: Graph) -> dict:
    """Map each declared class/property IRI in the graph to 'class' or 'property'.

    Restricted to non-well-known namespaces (the ontology under test, not the
    RDF/RDFS/OWL/SKOS vocabulary it is written in).
    """
    terms = {}
    for t in CLASS_TYPES:
        for s in graph.subjects(RDF.type, t):
            if _is_domain_term(s):
                terms.setdefault(str(s), "class")
    for t in PROPERTY_TYPES:
        for s in graph.subjects(RDF.type, t):
            if _is_domain_term(s):
                terms[str(s)] = "property"  # a property label wins over a class collision
    return terms


def metadata_terms(graph: Graph) -> dict:
    """Domain terms declared *only* as annotation/ontology properties.

    Maps each such IRI to a reason label ("annotation property" /
    "ontology property"). These are documentation/metadata vocabulary, not the
    substantive classes and properties CQs exercise, so coverage reports an
    unused one as a schema term rather than a gap. A term also declared as a
    class or a substantive property is excluded — it is not "just metadata".
    """
    meta = {}
    for typ, label in METADATA_PROPERTY_TYPES.items():
        for s in graph.subjects(RDF.type, typ):
            if _is_domain_term(s):
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


def _shortener(graphs, query_texts=()):
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


def schema_references(tbox: Graph, used: set, declared: dict, short) -> dict:
    """Declared terms that structurally support a *used* term via TBox axioms.

    These are not directly instantiated or queried, but they are not dead
    weight either — they define the schema of terms the CQs do use, which is
    what makes them valuable for documentation and inferencing. Two sources:

      * domain / range of a used property, and
      * a superclass of a used class.

    Returns {term_iri: [reason, ...]} for terms that qualify. Reasons list
    domain/range before superclass, most relevant first.
    """
    declared_set = set(declared)
    reasons = {}
    for u in used:
        node = URIRef(u)
        kind = declared.get(u)
        if kind == "property":
            for d in tbox.objects(node, RDFS.domain):
                _add_reason(reasons, declared_set, d, f"domain of {short(u)}")
            for r in tbox.objects(node, RDFS.range):
                _add_reason(reasons, declared_set, r, f"range of {short(u)}")
        elif kind == "class":
            for anc in tbox.transitive_objects(node, RDFS.subClassOf):
                if str(anc) != u:
                    _add_reason(reasons, declared_set, anc, f"superclass of {short(u)}")
    return reasons


def _add_reason(reasons: dict, declared_set: set, term, reason: str) -> None:
    """Record `reason` for a declared `term` (deduped), skipping non-declared."""
    if str(term) in declared_set:
        bucket = reasons.setdefault(str(term), [])
        if reason not in bucket:
            bucket.append(reason)


def requires_ontology_to_pass(data_terms: set, query_terms: set, declared: dict, tbox: Graph) -> bool:
    """Whether a CQ's query matches its data only via a TBox axiom.

    True when the query references a declared class that is NOT instantiated in
    the CQ's own data, yet a subclass of it IS — so the query can only match
    (e.g. through an `rdfs:subClassOf*` path) if the ontology's class hierarchy
    is loaded as an input. The ontology is deliberately not counted as input
    data, so this is surfaced separately as "requires ontology to pass".
    """
    data_classes = [d for d in data_terms if declared.get(d) == "class"]
    for q in query_terms:
        if q in data_terms or declared.get(q) != "class":
            continue
        qnode = URIRef(q)
        for d in data_classes:
            if d != q and qnode in set(tbox.transitive_objects(URIRef(d), RDFS.subClassOf)):
                return True
    return False


def _source_link(p, link_base=None) -> dict:
    """Display label + a link href relative to `link_base`.

    Markdown previewers (e.g. VS Code) block absolute `file://` links under their
    content-security policy, so we emit a RELATIVE href instead — resolved by the
    viewer against the report's own location. `link_base` should be the directory
    the link is relative to: the report file's directory for an `--md` file, or
    the cwd for terminal output (which linkifies cwd-relative paths). The label
    stays relative to the cwd for readability.
    """
    p = Path(p)
    base = Path(link_base) if link_base is not None else Path.cwd()
    try:
        label = os.path.relpath(p)
    except ValueError:  # e.g. different drive on Windows
        label = str(p)
    try:
        url = os.path.relpath(p, base)
    except ValueError:
        url = str(p)
    return {"path": label, "url": url}


def _derive_declared(given_graphs, ontology):
    """(declared, metadata) from the ontology when given, else the given graphs.

    metadata is restricted to declared terms.
    """
    declared, metadata = {}, {}
    for g in ([ontology] if ontology is not None else given_graphs):
        declared.update(declared_terms(g))
        metadata.update(metadata_terms(g))
    return declared, {t: r for t, r in metadata.items() if t in declared}


def _build_shortener(specs, given_graphs, ontology):
    all_queries = [q for s in specs for q in (s.get("queries") or []) if isinstance(q, str)]
    prefix_graphs = list(given_graphs)
    if ontology is not None:
        prefix_graphs.append(ontology)
    return _shortener(prefix_graphs, all_queries)


def _build_tbox(given_graphs, ontology):
    """Combined TBox (given graphs + ontology) for schema classification and for
    deciding whether a CQ leans on the ontology's class hierarchy to pass."""
    tbox = Graph()
    for g in given_graphs:
        tbox += g
    if ontology is not None:
        tbox += ontology
    return tbox


def _scan_specs(specs, declared_set):
    """Walk each spec's data + queries once. Returns the credited used sets, the
    domain-namespace terms referenced anywhere (split data/query), and per-spec
    reference tuples for the undeclared report. (Per-CQ usage lives in cq.py.)"""
    used_data, used_query = set(), set()
    referenced_data, referenced_query = set(), set()
    spec_refs = []
    for s in specs:
        g = s.get("given")
        raw_data = abox_terms(g) if isinstance(g, Graph) else set()
        raw_query = set()
        for q in (s.get("queries") or []):
            if isinstance(q, str):
                raw_query |= query_uris(q)
        s_data = {t for t in raw_data if _is_domain_term(URIRef(t))}
        s_query = {t for t in raw_query if _is_domain_term(URIRef(t))}
        referenced_data |= s_data
        referenced_query |= s_query
        spec_refs.append((s.get("name", "?"), s.get("source_file"), s_data, s_query))
        if s.get("passed"):
            used_data |= raw_data & declared_set
            used_query |= raw_query & declared_set
    return used_data, used_query, referenced_data, referenced_query, spec_refs


def _fold_metadata_into_schema(schema_reasons, metadata, used):
    """Annotation/ontology properties no CQ exercises are metadata, not gaps —
    fold them into the schema bucket (excluded from the %) with their own reason."""
    for t, label in metadata.items():
        if t in used:
            continue
        bucket = schema_reasons.setdefault(t, [])
        if label not in bucket:
            bucket.append(label)


def _reason_key(r):
    return (0 if r.startswith("domain") else 1 if r.startswith("range") else 2, r)


def _usage_by_term(specs, declared_set):
    """Map each declared term to the *passing* tests that exercise it.

    Used to link a term to the tests behind it — the covering tests in the Test
    Term Coverage column, and the non-CQ backer of a CQ-scoped gap.
    Returns {term_iri: [{name, source_file, in_data, in_query}, ...]}.
    """
    refs_by_term = {}
    for s in specs:
        if not s.get("passed"):
            continue
        g = s.get("given")
        d = {t for t in (abox_terms(g) if isinstance(g, Graph) else set())
             if _is_domain_term(URIRef(t))} & declared_set
        q = set()
        for query in (s.get("queries") or []):
            if isinstance(query, str):
                q |= {t for t in query_uris(query) if _is_domain_term(URIRef(t))}
        q &= declared_set
        for t in d | q:
            refs_by_term.setdefault(t, []).append({
                "name": s.get("name", "?"),
                "source_file": str(s.get("source_file")) if s.get("source_file") else None,
                "in_data": t in d, "in_query": t in q})
    return refs_by_term


def _tbox_axioms(g, short):
    """The TBox (schema) axioms in one given graph, as readable strings —
    class/property declarations and rdfs:subClassOf/domain/range on domain terms."""
    axioms = set()
    for ty in TBOX_TYPES:
        axioms.update(f"{short(str(s))} a {_wk_qname(ty)}"
                      for s in g.subjects(RDF.type, ty) if _is_domain_term(s))
    for pred in TBOX_PREDICATES:
        for subj, obj in g.subject_objects(pred):
            if _is_domain_term(subj):
                tail = short(str(obj)) if isinstance(obj, URIRef) else str(obj)
                axioms.add(f"{short(str(subj))} {_wk_qname(pred)} {tail}")
    return sorted(axioms)


def _tbox_in_data(specs, short):
    """Find TBox (schema) axioms sitting in tests' input data.

    A `given` should hold instance data; class/property declarations and
    `rdfs:subClassOf`/`domain`/`range` axioms belong in the ontology. When a
    query only matches through such an axiom (e.g. a `subClassOf*` path), the
    axiom has been smuggled into the fixture — worth surfacing so it can be moved.
    Returns [{name, source_file, axioms: ["place:Province rdfs:subClassOf …", …]}].
    """
    results = []
    for s in specs:
        g = s.get("given")
        if not isinstance(g, Graph):
            continue
        axioms = _tbox_axioms(g, short)
        if axioms:
            results.append({
                "name": s.get("name", "?"),
                "source_file": str(s.get("source_file")) if s.get("source_file") else None,
                "axioms": axioms})
    return results


def _class_forest(declared, used, short, tbox, extra_external=()):
    """Arrange declared classes into a subClassOf forest for the term matrix.

    Nodes are declared classes plus the *external* classes that a used class
    subclasses or a property's domain names (e.g. foaf:Person). Each class hangs
    under its alphabetically-first parent (extra parents are annotated, not
    duplicated). Returns (roots, children, extra_parents, external, nodes).
    """
    classes = {t for t in declared if declared[t] == "class"}
    external = set(extra_external)
    for c in (classes & used):
        for anc in tbox.transitive_objects(URIRef(c), RDFS.subClassOf):
            if str(anc) != c and str(anc) not in declared and _is_domain_term(anc):
                external.add(str(anc))
    nodes = classes | external

    children, roots, extra_parents = {}, [], {}
    for c in sorted(nodes, key=short):
        parents = sorted((str(p) for p in tbox.objects(URIRef(c), RDFS.subClassOf)
                          if str(p) in nodes and str(p) != c), key=short)
        if parents:
            children.setdefault(parents[0], []).append(c)
            if len(parents) > 1:
                extra_parents[c] = [short(p) for p in parents[1:]]
        else:
            roots.append(c)
    for kids in children.values():
        kids.sort(key=short)
    return roots, children, extra_parents, external, nodes


def _coverage_status(term, schema_only, in_data, in_query):
    """covered (populated in data) / query-only (named by a query, never
    instantiated) / schema (structural, excluded) / unused. Used for both the
    all-tests verdict and the CQ-only verdict, over the relevant data/query sets."""
    if term in schema_only:
        return "schema"
    if term in in_data:
        return "covered"
    if term in in_query:
        return "query-only"
    return "unused"


def _matrix_row(term, kind, depth, connector, ctx, external=False):
    """One term's matrix row (columns + depth + connector). External = schema."""
    if external:
        return {"depth": depth, "kind": kind, "term": ctx["short"](term), "external": True,
                "connector": connector, "in_data": False, "in_query": False,
                "in_schema": True, "status": "schema", "cq_status": "schema",
                "by_cq_state": "schema"}
    schema_only, used_data, used_query = ctx["schema_only"], ctx["used_data"], ctx["used_query"]
    cq_data, cq_query = ctx["cq_used_data"], ctx["cq_used_query"]
    status = _coverage_status(term, schema_only, used_data, used_query)
    cq_status = _coverage_status(term, schema_only, cq_data, cq_query)
    row = {"depth": depth, "kind": kind, "term": ctx["short"](term), "external": False,
           "connector": connector, "in_data": term in used_data,
           "in_query": term in used_query, "in_schema": term in schema_only,
           "status": status, "cq_status": cq_status,
           "by_cq_state": "schema" if term in schema_only else ("yes" if term in cq_data else "no")}
    if term in ctx["extra_parents"]:
        row["extra_parents"] = ctx["extra_parents"][term]
    # Link the tests behind this term, each tagged with what it contributes
    # (data / SPARQL / both). Listing every referencing test — not just the data
    # ones — makes a split visible: a term whose data and SPARQL come from
    # *different* tests reads as "fully exercised" in the aggregate columns, but
    # its per-test tags show no single test does both.
    refs = ctx["test_refs"].get(term, [])
    if refs and status in ("covered", "query-only"):
        row["cover_refs"] = sorted(refs, key=lambda r: r["name"])
    return row


def _walk_forest(node, depth, children, attached, ctx, rows):
    """Emit `node`, its attached properties (▸), and its subclass subtree (↳).
    A linear run of schema-only ancestors with no attached property collapses
    into one grouped row — a property forces its domain class to stay visible."""
    external, schema_only, short = ctx["external"], ctx["schema_only"], ctx["short"]

    def collapsible(c):
        return (c in external or c in schema_only) and len(children.get(c, [])) == 1 and not attached.get(c)

    run, cur = [], node
    while collapsible(cur):
        run.append(cur)
        cur = children[cur][0]
    if len(run) >= 2:
        rows.append({"depth": depth, "kind": "class", "grouped": True,
                     "term": ", ".join(short(c) for c in run),
                     "external": all(c in external for c in run),
                     "connector": "sub" if depth else None,
                     "in_data": False, "in_query": False, "in_schema": True,
                     "status": "schema", "cq_status": "schema", "by_cq_state": "schema"})
        _walk_forest(cur, depth + 1, children, attached, ctx, rows)
    else:
        rows.append(_matrix_row(node, "class", depth, "sub" if depth else None, ctx,
                                external=node in external))
        for prop in attached.get(node, []):
            rows.append(_matrix_row(prop, "property", depth + 1, "prop", ctx))
        for child in children.get(node, []):
            _walk_forest(child, depth + 1, children, attached, ctx, rows)


def _ordered_terms(declared, referenced, used_data, used_query, cq_used_data, cq_used_query, schema_only, test_refs, short, tbox):
    """The per-term matrix as an ordered list of rows: an indented subClassOf
    tree of classes, each with its domain-attached properties (▸) beneath it;
    properties with no domain trail at the end. `referenced` (data ∪ query) drives
    the class tree's external-ancestor detection; coverage status is data-based."""
    props = [t for t in declared if declared[t] == "property"]
    ext_domains = {str(d) for p in props for d in tbox.objects(URIRef(p), RDFS.domain)
                   if str(d) not in declared and _is_domain_term(d)}
    roots, children, extra_parents, external, nodes = \
        _class_forest(declared, referenced, short, tbox, ext_domains)

    attached, unattached = {}, []
    for p in sorted(props, key=short):
        domains = sorted((str(d) for d in tbox.objects(URIRef(p), RDFS.domain) if str(d) in nodes),
                         key=short)
        (attached.setdefault(domains[0], []).append(p) if domains else unattached.append(p))

    ctx = {"used_data": used_data, "used_query": used_query,
           "cq_used_data": cq_used_data, "cq_used_query": cq_used_query,
           "schema_only": schema_only, "test_refs": test_refs, "short": short,
           "external": external, "extra_parents": extra_parents}
    rows = []
    for root in roots:
        _walk_forest(root, 0, children, attached, ctx, rows)
    for p in unattached:
        rows.append(_matrix_row(p, "property", 0, None, ctx))
    return rows


def _schema_term_rows(schema_only, schema_reasons, declared, short):
    return [{"term": short(t), "kind": declared[t],
             "reason": "; ".join(sorted(schema_reasons[t], key=_reason_key)[:3])}
            for t in sorted(schema_only)]


def _build_undeclared(referenced_data, referenced_query, declared, declared_set, spec_refs, short):
    """Terms a CQ references (in data or SPARQL) that fall in a declared ontology's
    namespace but are not themselves declared — likely typos or missing
    definitions. External vocabularies (other namespaces) are ignored. Each is
    tagged with where it was referenced and which CQs reference it."""
    ontology_namespaces = {_namespace(t) for t in declared}
    iris = [t for t in (referenced_data | referenced_query)
            if t not in declared_set and _namespace(t) in ontology_namespaces]
    undeclared = []
    for t in sorted(iris, key=short):
        refs = [{"name": name, "source_file": str(src) if src else None,
                 "in_data": t in sd, "in_query": t in sq}
                for (name, src, sd, sq) in spec_refs if t in sd or t in sq]
        undeclared.append({"term": short(t), "refs": refs})
    return undeclared


def compute_coverage(specs: List[dict], ontology: Optional[Graph] = None,
                     cq_defs: Optional[List[dict]] = None) -> Optional[dict]:
    """Ontology term coverage across ALL mustrd tests.

    `specs` is a list of dicts: {name, uri, passed, given (Graph), queries [str]}
    — every mustrd test in the suite; coverage is measured over them.
    `ontology` is the graph whose declared terms coverage is measured against;
    when omitted (e.g. in unit tests), declared terms fall back to the union of
    the specs' given graphs.
    `cq_defs` is the list of competency-question nodes — each
    {id, name, question, questions, specs (linked spec dicts), missing_specs}.
    When given, it adds a CQ overlay: per-term CQ coverage, a CQ coverage
    percentage, the per-CQ breakdown, and duplicate-question detection. CQ nodes
    sharing a question are excluded from that overlay (likely copy/paste).

    Returns a template context dict, or None if no ontology terms are declared.
    """
    given_graphs = [s["given"] for s in specs if isinstance(s.get("given"), Graph)]
    declared, metadata = _derive_declared(given_graphs, ontology)
    if not declared:
        return None

    short = _build_shortener(specs, given_graphs, ontology)
    tbox = _build_tbox(given_graphs, ontology)
    declared_set = set(declared)

    # Coverage over every test. A term is COVERED when a passing test populates
    # it in its input data (data-only counts — a property-path query may consume
    # the instance by IRI without naming the class; we revisit that with mutation
    # testing). A term named only in a query, never instantiated, is *not* covered
    # (the test can pass without it) — it is a query-only gap. `referenced` is the
    # looser union (data ∪ query), used for structural support and the class tree.
    used_data, used_query, referenced_data, referenced_query, spec_refs = \
        _scan_specs(specs, declared_set)
    referenced = used_data | used_query

    # CQ overlay (built in cq.py): which declared terms competency questions
    # exercise, the per-CQ breakdown, and the duplicate-question warning. Imported
    # locally so coverage.py stays free of a module-load dependency on cq.py.
    from mustrd.cq import compute_cq_overlay
    overlay = compute_cq_overlay(cq_defs or [], declared_set, declared, tbox, short)
    cq_used_data, cq_used_query = overlay["cq_used_data"], overlay["cq_used_query"]
    per_cq, duplicate_cqs = overlay["per_cq"], overlay["duplicate_cqs"]

    schema_reasons = schema_references(tbox, referenced, declared, short)
    _fold_metadata_into_schema(schema_reasons, metadata, referenced)
    schema_only = {t for t in schema_reasons if t not in referenced}

    # Which passing tests back each term: all tests (for the Test Term Coverage
    # links) and non-CQ tests only (to name the backer of a CQ-scoped gap).
    test_refs = _usage_by_term(specs, declared_set)
    non_cq_refs = _usage_by_term(
        [s for s in specs if s.get("uri") not in overlay["cq_uris"]], declared_set)
    terms = _ordered_terms(declared, referenced, used_data, used_query, cq_used_data,
                           cq_used_query, schema_only, test_refs, short, tbox)
    # "Not covered by any test": declared, non-structural terms no passing test
    # populates in data. Query-only terms (named by a query but never instantiated)
    # land here too, flagged so the report can distinguish them from the untouched.
    gaps = [{"term": short(t), "kind": declared[t], "query_only": t in used_query}
            for t in sorted(declared) if t not in used_data and t not in schema_only]
    # CQ-scoped gaps: declared, non-structural terms no competency question covers
    # in data. Where a non-CQ test does cover it, carry that test so the report can
    # name it; where only a CQ *query* names it, flag it query-only.
    cq_gaps = []
    for t in sorted(declared):
        if t in schema_only or t in cq_used_data:
            continue
        entry = {"term": short(t), "kind": declared[t], "query_only": t in cq_used_query}
        if t in non_cq_refs:
            entry["non_cq_refs"] = non_cq_refs[t]
        cq_gaps.append(entry)
    schema_terms = _schema_term_rows(schema_only, schema_reasons, declared, short)
    undeclared = _build_undeclared(referenced_data, referenced_query, declared,
                                   declared_set, spec_refs, short)

    denominator = len(declared) - len(schema_only)  # schema-only terms excluded
    covered = sum(1 for t in declared if t in used_data)
    covered_by_cq = sum(1 for t in declared if t in cq_used_data)

    return {
        "covered": covered, "denominator": denominator,
        "pct": round(100.0 * covered / denominator) if denominator else 0,
        "declared_total": len(declared), "schema_count": len(schema_only),
        "has_cq": bool(cq_defs),
        "covered_by_cq": covered_by_cq,
        "cq_pct": round(100.0 * covered_by_cq / denominator) if denominator else 0,
        "terms": terms, "gaps": gaps, "cq_gaps": cq_gaps, "schema_terms": schema_terms,
        "undeclared": undeclared, "duplicate_cqs": duplicate_cqs,
        "tbox_in_data": _tbox_in_data(specs, short),
        "per_cq": per_cq,
    }
