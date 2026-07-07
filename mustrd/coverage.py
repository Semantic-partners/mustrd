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
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from rdflib import Graph, URIRef, RDF, RDFS, OWL, XSD
from rdflib.plugins.sparql import prepareQuery

log = logging.getLogger(__name__)

# RDF serialisations recognised when scanning an ontology directory.
ONTOLOGY_SUFFIXES = {".ttl", ".trig", ".nt", ".nq", ".n3", ".jsonld", ".rdf", ".owl", ".xml"}

# Namespaces whose terms are infrastructure, not "the ontology under test".
WELL_KNOWN = (
    str(RDF), str(RDFS), str(OWL), str(XSD),
    "http://www.w3.org/2004/02/skos/core#",
    "http://www.w3.org/ns/shacl#",
    "http://www.w3.org/2002/07/owl#",
    "https://mustrd.org/model/",
    "http://purl.org/dc/elements/1.1/",
    "http://purl.org/dc/terms/",
    "http://www.w3.org/ns/prov#",
)

CLASS_TYPES = (OWL.Class, RDFS.Class)
PROPERTY_TYPES = (
    OWL.ObjectProperty, OWL.DatatypeProperty, OWL.TransitiveProperty,
    OWL.AnnotationProperty, OWL.FunctionalProperty, OWL.SymmetricProperty,
    RDF.Property,
)


@dataclass
class SpecUsage:
    """One spec's contribution to coverage."""
    name: str
    competency_question: Optional[str]
    passed: bool
    data_terms: List[str] = field(default_factory=list)
    query_terms: List[str] = field(default_factory=list)


def _is_domain_term(uri) -> bool:
    return isinstance(uri, URIRef) and not any(str(uri).startswith(ns) for ns in WELL_KNOWN)


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


def query_uris(query_text: str) -> set:
    """Every IRI referenced in a query's parsed algebra (ignores comments).

    Handles SELECT/CONSTRUCT/ASK/DESCRIBE and, as a fallback, SPARQL Update.
    """
    algebra = None
    try:
        algebra = prepareQuery(query_text).algebra
    except Exception:
        try:
            from rdflib.plugins.sparql.parser import parseUpdate
            from rdflib.plugins.sparql.algebra import translateUpdate
            algebra = translateUpdate(parseUpdate(query_text))
        except Exception:
            return set()

    found = set()

    def walk(obj, seen):
        if id(obj) in seen:
            return
        seen.add(id(obj))
        if isinstance(obj, URIRef):
            found.add(str(obj))
        elif isinstance(obj, dict):
            for v in obj.values():
                walk(v, seen)
        elif isinstance(obj, (list, tuple, set)):
            for v in obj:
                walk(v, seen)
        elif hasattr(obj, "__dict__"):
            for v in vars(obj).values():
                walk(v, seen)

    walk(algebra, set())
    return found


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
    auto-generates `ns1`, `geo1`, ... on collisions), whereas the SPARQL
    `PREFIX geo: <...>` lines are author-chosen and clean. Per namespace we pick
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

    def add(term, reason):
        if str(term) in declared_set:
            reasons.setdefault(str(term), [])
            if reason not in reasons[str(term)]:
                reasons[str(term)].append(reason)

    for u in used:
        node = URIRef(u)
        if declared.get(u) == "property":
            for d in tbox.objects(node, RDFS.domain):
                add(d, f"domain of {short(u)}")
            for r in tbox.objects(node, RDFS.range):
                add(r, f"range of {short(u)}")
        elif declared.get(u) == "class":
            for anc in tbox.transitive_objects(node, RDFS.subClassOf):
                if str(anc) != u:
                    add(anc, f"superclass of {short(u)}")
    return reasons


def compute_coverage(specs: List[dict], ontology: Optional[Graph] = None) -> Optional[dict]:
    """Compute term coverage across specs.

    `specs` is a list of dicts: {name, cq, passed, given (Graph), queries [str]}.
    `ontology` is the graph whose declared terms coverage is measured against;
    when given, declared terms come from it. When omitted (e.g. in unit tests),
    declared terms fall back to the union of the specs' given graphs.

    Returns a template context dict, or None if no ontology terms are declared
    (nothing to measure).
    """
    given_graphs = [s["given"] for s in specs if isinstance(s.get("given"), Graph)]

    declared = {}
    if ontology is not None:
        declared.update(declared_terms(ontology))
    else:
        for g in given_graphs:
            declared.update(declared_terms(g))
    if not declared:
        return None

    all_queries = [q for s in specs for q in (s.get("queries") or []) if isinstance(q, str)]
    prefix_graphs = given_graphs + ([ontology] if ontology is not None else [])
    short = _shortener(prefix_graphs, all_queries)

    used_data, used_query = set(), set()
    per_cq = []
    declared_set = set(declared)
    for s in specs:
        g = s.get("given")
        queries = s.get("queries") or []
        d_terms = (abox_terms(g) & declared_set) if isinstance(g, Graph) else set()
        q_terms = set()
        for q in queries:
            if isinstance(q, str):
                q_terms |= query_uris(q)
        q_terms &= declared_set
        credited = bool(s.get("passed"))
        if credited:
            used_data |= d_terms
            used_query |= q_terms
        per_cq.append(SpecUsage(
            name=s.get("name", "?"),
            competency_question=s.get("cq"),
            passed=credited,
            data_terms=sorted(short(t) for t in d_terms),
            query_terms=sorted(short(t) for t in q_terms),
        ))

    used = used_data | used_query

    # Third category: terms not directly exercised, but referenced structurally
    # in the schema of a USED term (domain/range of a used property, superclass
    # of a used class). These are excluded from the coverage denominator.
    tbox = Graph()
    for g in given_graphs:
        tbox += g
    if ontology is not None:
        tbox += ontology
    schema_reasons = schema_references(tbox, used, declared, short)
    schema_only = {t for t in schema_reasons if t not in used}

    def status(t):
        if t in used:
            return "covered"
        if t in schema_only:
            return "schema"
        return "unused"

    terms = []
    for t in sorted(declared, key=lambda x: (declared[x], short(x))):
        terms.append({
            "term": short(t), "kind": declared[t],
            "in_data": t in used_data, "in_query": t in used_query,
            "in_schema": t in schema_only, "status": status(t),
        })

    gaps = [{"term": short(t), "kind": declared[t]}
            for t in sorted(declared) if status(t) == "unused"]
    def _reason_key(r):
        return (0 if r.startswith("domain") else 1 if r.startswith("range") else 2, r)

    schema_terms = [{"term": short(t), "kind": declared[t],
                     "reason": "; ".join(sorted(schema_reasons[t], key=_reason_key)[:3])}
                    for t in sorted(schema_only)]

    covered = sum(1 for t in declared if t in used)
    denominator = len(declared) - len(schema_only)  # schema-only terms excluded
    pct = round(100.0 * covered / denominator) if denominator else 0

    return {
        "covered": covered, "denominator": denominator, "pct": pct,
        "declared_total": len(declared), "schema_count": len(schema_only),
        "terms": terms, "gaps": gaps, "schema_terms": schema_terms,
        "per_cq": [{
            "name": u.name, "cq": u.competency_question, "status": _status(u),
            "credited": u.passed, "data": u.data_terms, "query": u.query_terms,
        } for u in per_cq],
    }


def _status(u: SpecUsage) -> str:
    return "passed" if u.passed else "not passed"
