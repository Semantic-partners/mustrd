"""Ontology term coverage from competency-question specs.

See docs/ontology-term-coverage.md for the design. In short: given the specs
mustrd already parsed, work out which ontology terms the *passing* CQ tests
actually exercise — in their input data (ABox) or their SPARQL — and which
declared terms nothing touches.

A term is COVERED if a passing spec references it either:
  * in the input data: as an object of rdf:type, or as an asserted predicate; or
  * in the SPARQL query: as an IRI in the parsed query algebra.

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
from dataclasses import dataclass, field
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


@dataclass
class SpecUsage:
    """One spec's contribution to coverage."""
    name: str
    competency_question: Optional[str]
    passed: bool
    data_terms: List[str] = field(default_factory=list)
    query_terms: List[str] = field(default_factory=list)
    requires_ontology: bool = False


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


def _scan_specs(specs, declared_set, declared, tbox, short):
    """Walk each spec's data + queries once. Returns the credited used sets, the
    domain-namespace terms referenced anywhere (split data/query), one SpecUsage
    per spec, and per-spec reference tuples for the undeclared report."""
    used_data, used_query = set(), set()
    referenced_data, referenced_query = set(), set()
    spec_refs, per_cq = [], []
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
        d_terms = raw_data & declared_set
        q_terms = raw_query & declared_set
        if s.get("passed"):
            used_data |= d_terms
            used_query |= q_terms
        per_cq.append(SpecUsage(
            name=s.get("name", "?"),
            competency_question=s.get("cq"),
            passed=bool(s.get("passed")),
            data_terms=sorted(short(t) for t in d_terms),
            query_terms=sorted(short(t) for t in q_terms),
            requires_ontology=requires_ontology_to_pass(d_terms, q_terms, declared, tbox),
        ))
    return used_data, used_query, referenced_data, referenced_query, per_cq, spec_refs


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


def _non_cq_usage(non_cq_specs, declared_set):
    """Map each declared term to the *passing* non-CQ tests that exercise it.

    Used to explain a covered-but-not-by-a-CQ term: which plain test backs it.
    Returns {term_iri: [{name, source_file, in_data, in_query}, ...]}.
    """
    refs_by_term = {}
    for s in non_cq_specs:
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


def _class_forest(declared, used, short, tbox):
    """Arrange declared classes into a subClassOf forest for the term matrix.

    Nodes are declared classes plus the *external* superclasses of used classes
    (e.g. foaf:Person). Each class hangs under its alphabetically-first parent
    (extra parents are annotated, not duplicated). Returns
    (roots, children, extra_parents, external), all keyed by term IRI.
    """
    classes = {t for t in declared if declared[t] == "class"}
    external = set()
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
    return roots, children, extra_parents, external


def _matrix_row(term, kind, depth, ctx, external=False):
    """One term's matrix row (columns + depth). External terms are schema."""
    if external:
        return {"depth": depth, "kind": kind, "term": ctx["short"](term), "external": True,
                "in_data": False, "in_query": False, "in_schema": True,
                "status": "schema", "by_cq_state": "schema"}
    schema_only, used, cq_used = ctx["schema_only"], ctx["used"], ctx["cq_used"]
    status = "covered" if term in used else ("schema" if term in schema_only else "unused")
    row = {"depth": depth, "kind": kind, "term": ctx["short"](term), "external": False,
           "in_data": term in ctx["used_data"], "in_query": term in ctx["used_query"],
           "in_schema": term in schema_only, "status": status,
           "by_cq_state": "schema" if term in schema_only else ("yes" if term in cq_used else "no")}
    if term in ctx["extra_parents"]:
        row["extra_parents"] = ctx["extra_parents"][term]
    if row["by_cq_state"] == "no" and term in ctx["non_cq_refs"]:
        row["non_cq_refs"] = ctx["non_cq_refs"][term]
    return row


def _walk_forest(node, depth, children, ctx, rows):
    """Emit `node` and its subtree, collapsing a linear run of schema-only
    ancestors (each with a single child) into one grouped row."""
    external, schema_only, short = ctx["external"], ctx["schema_only"], ctx["short"]
    run, cur = [], node
    while (cur in external or cur in schema_only) and len(children.get(cur, [])) == 1:
        run.append(cur)
        cur = children[cur][0]
    if len(run) >= 2:
        rows.append({"depth": depth, "kind": "class", "grouped": True,
                     "term": ", ".join(short(c) for c in run),
                     "external": all(c in external for c in run),
                     "in_data": False, "in_query": False, "in_schema": True,
                     "status": "schema", "by_cq_state": "schema"})
        _walk_forest(cur, depth + 1, children, ctx, rows)
    else:
        rows.append(_matrix_row(node, "class", depth, ctx, external=node in external))
        for child in children.get(node, []):
            _walk_forest(child, depth + 1, children, ctx, rows)


def _ordered_terms(declared, used, used_data, used_query, cq_used, schema_only, non_cq_refs, short, tbox):
    """The per-term matrix as an ordered list of rows: classes first, arranged as
    an indented subClassOf tree (a linear run of schema-only ancestors collapses
    into one grouped row), then properties flat."""
    roots, children, extra_parents, external = _class_forest(declared, used, short, tbox)
    ctx = {"used": used, "used_data": used_data, "used_query": used_query, "cq_used": cq_used,
           "schema_only": schema_only, "non_cq_refs": non_cq_refs, "short": short,
           "external": external, "extra_parents": extra_parents}
    rows = []
    for root in roots:
        _walk_forest(root, 0, children, ctx, rows)
    for p in sorted((t for t in declared if declared[t] == "property"), key=short):
        rows.append(_matrix_row(p, "property", 0, ctx))
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


def _split_duplicate_cqs(specs):
    """Partition specs into (duplicate_cqs, kept).

    A competency-question value shared by more than one spec is almost always a
    copy/paste error, so every spec carrying a duplicated value is dropped from
    the calculation. `duplicate_cqs` describes what was excluded, for a warning:
    [{cq, specs: [{name, source_file}, ...]}].
    """
    counts = {}
    for s in specs:
        counts[s.get("cq")] = counts.get(s.get("cq"), 0) + 1
    dup_values = {cq for cq, n in counts.items() if cq is not None and n > 1}
    kept = [s for s in specs if s.get("cq") not in dup_values]
    duplicate_cqs = [{
        "cq": cq,
        "specs": [{"name": s.get("name", "?"),
                   "source_file": str(s.get("source_file")) if s.get("source_file") else None}
                  for s in specs if s.get("cq") == cq],
    } for cq in sorted(dup_values)]
    return duplicate_cqs, kept


def _serialize_per_cq(per_cq):
    return [{"name": u.name, "cq": u.competency_question, "status": _status(u),
             "credited": u.passed, "data": u.data_terms, "query": u.query_terms,
             "requires_ontology": u.requires_ontology} for u in per_cq]


def compute_coverage(specs: List[dict], ontology: Optional[Graph] = None,
                     cq_specs: Optional[List[dict]] = None) -> Optional[dict]:
    """Ontology term coverage across ALL mustrd tests.

    `specs` is a list of dicts: {name, passed, given (Graph), queries [str]} —
    every mustrd test in the suite; coverage is measured over them.
    `ontology` is the graph whose declared terms coverage is measured against;
    when omitted (e.g. in unit tests), declared terms fall back to the union of
    the specs' given graphs.
    `cq_specs` is the competency-question subset (each also carrying a `cq`
    value). When given, it adds a CQ overlay: per-term `by_cq`, a CQ coverage
    percentage, the per-CQ breakdown, and duplicate-CQ detection. CQs sharing a
    value are excluded from that overlay (likely copy/paste).

    Returns a template context dict, or None if no ontology terms are declared.
    """
    given_graphs = [s["given"] for s in specs if isinstance(s.get("given"), Graph)]
    declared, metadata = _derive_declared(given_graphs, ontology)
    if not declared:
        return None

    all_specs = specs + [s for s in (cq_specs or []) if s not in specs]
    short = _build_shortener(all_specs, given_graphs, ontology)
    tbox = _build_tbox(given_graphs, ontology)
    declared_set = set(declared)

    # Coverage over every test.
    used_data, used_query, referenced_data, referenced_query, _, spec_refs = \
        _scan_specs(specs, declared_set, declared, tbox, short)
    used = used_data | used_query

    # CQ overlay: which declared terms competency questions exercise (deduped).
    duplicate_cqs, cq_kept = _split_duplicate_cqs(cq_specs or [])
    cq_used_data, cq_used_query, _, _, per_cq, _ = \
        _scan_specs(cq_kept, declared_set, declared, tbox, short)
    cq_used = cq_used_data | cq_used_query

    schema_reasons = schema_references(tbox, used, declared, short)
    _fold_metadata_into_schema(schema_reasons, metadata, used)
    schema_only = {t for t in schema_reasons if t not in used}

    non_cq_refs = _non_cq_usage([s for s in specs if s not in (cq_specs or [])], declared_set)
    terms = _ordered_terms(declared, used, used_data, used_query, cq_used,
                           schema_only, non_cq_refs, short, tbox)
    gaps = [{"term": short(t), "kind": declared[t]}
            for t in sorted(declared) if t not in used and t not in schema_only]
    # CQ-scoped gaps: declared, non-schema terms no competency question exercises
    # (a superset of `gaps` — includes terms only a non-CQ test covers). Where a
    # non-CQ test does exercise it, carry that test so the report can name it.
    cq_gaps = []
    for t in sorted(declared):
        if t in schema_only or t in cq_used:
            continue
        entry = {"term": short(t), "kind": declared[t]}
        if t in non_cq_refs:
            entry["non_cq_refs"] = non_cq_refs[t]
        cq_gaps.append(entry)
    schema_terms = _schema_term_rows(schema_only, schema_reasons, declared, short)
    undeclared = _build_undeclared(referenced_data, referenced_query, declared,
                                   declared_set, spec_refs, short)

    denominator = len(declared) - len(schema_only)  # schema-only terms excluded
    covered = sum(1 for t in declared if t in used)
    covered_by_cq = sum(1 for t in declared if t in cq_used)

    return {
        "covered": covered, "denominator": denominator,
        "pct": round(100.0 * covered / denominator) if denominator else 0,
        "declared_total": len(declared), "schema_count": len(schema_only),
        "has_cq": bool(cq_specs),
        "covered_by_cq": covered_by_cq,
        "cq_pct": round(100.0 * covered_by_cq / denominator) if denominator else 0,
        "terms": terms, "gaps": gaps, "cq_gaps": cq_gaps, "schema_terms": schema_terms,
        "undeclared": undeclared, "duplicate_cqs": duplicate_cqs,
        "per_cq": _serialize_per_cq(per_cq),
    }


def cq_only_view(cq_specs: List[dict]) -> dict:
    """Competency-question breakdown WITHOUT an ontology (for --cq on its own).

    Lists every non-well-known term each CQ references — unchecked, so it may
    include terms no ontology declares — plus duplicate-CQ detection. `unchecked`
    flags that no ontology was consulted, so the report can say so.
    """
    given_graphs = [s["given"] for s in cq_specs if isinstance(s.get("given"), Graph)]
    all_queries = [q for s in cq_specs for q in (s.get("queries") or []) if isinstance(q, str)]
    short = _shortener(given_graphs, all_queries)
    duplicate_cqs, kept = _split_duplicate_cqs(cq_specs)
    per_cq = []
    for s in kept:
        g = s.get("given")
        d = {t for t in (abox_terms(g) if isinstance(g, Graph) else set()) if _is_domain_term(URIRef(t))}
        q = set()
        for query in (s.get("queries") or []):
            if isinstance(query, str):
                q |= {t for t in query_uris(query) if _is_domain_term(URIRef(t))}
        per_cq.append({"name": s.get("name", "?"), "cq": s.get("cq"),
                       "status": "passed" if s.get("passed") else "not passed",
                       "credited": bool(s.get("passed")),
                       "data": sorted(short(t) for t in d),
                       "query": sorted(short(t) for t in q),
                       "requires_ontology": False})
    return {"per_cq": per_cq, "duplicate_cqs": duplicate_cqs, "unchecked": True}


def _status(u: SpecUsage) -> str:
    return "passed" if u.passed else "not passed"
