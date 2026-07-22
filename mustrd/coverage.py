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
    """Map each declared term to the non-CQ specs that exercise it (data/query).

    Non-CQ mustrd tests never count toward coverage, but when one exercises a
    term no CQ does, that is worth surfacing — the term is not truly dead.
    Returns {term_iri: [{name, source_file, in_data, in_query}, ...]}.
    """
    refs_by_term = {}
    for s in non_cq_specs or []:
        g = s.get("given")
        s_data = {t for t in (abox_terms(g) if isinstance(g, Graph) else set())
                  if _is_domain_term(URIRef(t))} & declared_set
        s_query = set()
        for q in (s.get("queries") or []):
            if isinstance(q, str):
                s_query |= {t for t in query_uris(q) if _is_domain_term(URIRef(t))}
        s_query &= declared_set
        for t in s_data | s_query:
            refs_by_term.setdefault(t, []).append({
                "name": s.get("name", "?"),
                "source_file": str(s.get("source_file")) if s.get("source_file") else None,
                "in_data": t in s_data, "in_query": t in s_query,
            })
    return refs_by_term


def _classify_terms(declared, used, used_data, used_query, schema_only, short, non_cq_refs):
    """Per-term matrix rows and the list of genuine gaps. An unused term that a
    non-CQ test exercises carries that test's references (for the status note)."""
    def status(t):
        if t in used:
            return "covered"
        return "schema" if t in schema_only else "unused"

    def row(t):
        r = {"term": short(t), "kind": declared[t],
             "in_data": t in used_data, "in_query": t in used_query,
             "in_schema": t in schema_only, "status": status(t)}
        if r["status"] == "unused" and t in non_cq_refs:
            r["non_cq_refs"] = non_cq_refs[t]
        return r

    terms = [row(t) for t in sorted(declared, key=lambda x: (declared[x], short(x)))]
    gaps = [{"term": short(t), "kind": declared[t]}
            for t in sorted(declared) if status(t) == "unused"]
    return terms, gaps


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


def compute_coverage(specs: List[dict], ontology: Optional[Graph] = None,
                     non_cq_specs: Optional[List[dict]] = None) -> Optional[dict]:
    """Compute term coverage across specs.

    `specs` is a list of dicts: {name, cq, passed, given (Graph), queries [str]}
    — the competency-question specs coverage is measured over. `non_cq_specs` is
    the same shape for mustrd tests WITHOUT a competency question; they never
    count toward coverage, but a term only they exercise is noted on its (unused)
    row rather than looking wholly dead.
    `ontology` is the graph whose declared terms coverage is measured against;
    when given, declared terms come from it. When omitted (e.g. in unit tests),
    declared terms fall back to the union of the specs' given graphs.

    Returns a template context dict, or None if no ontology terms are declared
    (nothing to measure).
    """
    # Specs sharing a competency-question value are excluded (likely copy/paste).
    duplicate_cqs, specs = _split_duplicate_cqs(specs)

    given_graphs = [s["given"] for s in specs if isinstance(s.get("given"), Graph)]
    declared, metadata = _derive_declared(given_graphs, ontology)
    if not declared:
        return None

    short = _build_shortener(specs, given_graphs, ontology)
    tbox = _build_tbox(given_graphs, ontology)
    declared_set = set(declared)

    used_data, used_query, referenced_data, referenced_query, per_cq, spec_refs = \
        _scan_specs(specs, declared_set, declared, tbox, short)
    used = used_data | used_query

    schema_reasons = schema_references(tbox, used, declared, short)
    _fold_metadata_into_schema(schema_reasons, metadata, used)
    schema_only = {t for t in schema_reasons if t not in used}

    non_cq_refs = _non_cq_usage(non_cq_specs, declared_set)
    terms, gaps = _classify_terms(declared, used, used_data, used_query,
                                  schema_only, short, non_cq_refs)
    schema_terms = _schema_term_rows(schema_only, schema_reasons, declared, short)
    undeclared = _build_undeclared(referenced_data, referenced_query, declared,
                                   declared_set, spec_refs, short)

    covered = sum(1 for t in declared if t in used)
    denominator = len(declared) - len(schema_only)  # schema-only terms excluded
    pct = round(100.0 * covered / denominator) if denominator else 0

    return {
        "covered": covered, "denominator": denominator, "pct": pct,
        "declared_total": len(declared), "schema_count": len(schema_only),
        "terms": terms, "gaps": gaps, "schema_terms": schema_terms,
        "undeclared": undeclared, "duplicate_cqs": duplicate_cqs,
        "per_cq": [{
            "name": u.name, "cq": u.competency_question, "status": _status(u),
            "credited": u.passed, "data": u.data_terms, "query": u.query_terms,
            "requires_ontology": u.requires_ontology,
        } for u in per_cq],
    }


def _status(u: SpecUsage) -> str:
    return "passed" if u.passed else "not passed"
