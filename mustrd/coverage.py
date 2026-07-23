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
from typing import List, Optional

from rdflib import Graph, URIRef, RDF, RDFS

from mustrd.ontology import (
    CLASS_TYPES, PROPERTY_TYPES,
    wk_qname, is_domain_term, namespace,
    declared_terms, metadata_terms, query_uris, abox_terms, shortener,
)


log = logging.getLogger(__name__)


# rdf:type objects and predicates that make a triple a TBox (schema) axiom. When
# these appear in a test's `given`, the fixture is defining ontology structure —
# which belongs in the ontology, not the test data — so the report hints they be
# moved. The type set is derived from ontology.PROPERTY_TYPES so it can't drift.
TBOX_TYPES = CLASS_TYPES + tuple(PROPERTY_TYPES)
TBOX_PREDICATES = (RDFS.subClassOf, RDFS.subPropertyOf, RDFS.domain, RDFS.range)


def _slug(qname: str) -> str:
    """A URL-path-safe slug for a term's qname (e.g. place:City -> place.City),
    used to mint stable per-term IRIs in the RDF output."""
    return "".join(c if (c.isalnum() or c in "._-") else "_"
                   for c in qname.replace(":", "."))


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
    return shortener(prefix_graphs, all_queries)


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
        s_data = {t for t in raw_data if is_domain_term(URIRef(t))}
        s_query = {t for t in raw_query if is_domain_term(URIRef(t))}
        referenced_data |= s_data
        referenced_query |= s_query
        spec_refs.append((s.get("name", "?"), s.get("source_file"), s_data, s_query, s.get("uri")))
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
             if is_domain_term(URIRef(t))} & declared_set
        q = set()
        for query in (s.get("queries") or []):
            if isinstance(query, str):
                q |= {t for t in query_uris(query) if is_domain_term(URIRef(t))}
        q &= declared_set
        for t in d | q:
            refs_by_term.setdefault(t, []).append({
                "name": s.get("name", "?"), "uri": s.get("uri"),
                "source_file": str(s.get("source_file")) if s.get("source_file") else None,
                "in_data": t in d, "in_query": t in q})
    return refs_by_term


def _tbox_axioms(g, short):
    """The TBox (schema) axioms in one given graph, as readable strings —
    class/property declarations and rdfs:subClassOf/domain/range on domain terms."""
    axioms = set()
    for ty in TBOX_TYPES:
        axioms.update(f"{short(str(s))} a {wk_qname(ty)}"
                      for s in g.subjects(RDF.type, ty) if is_domain_term(s))
    for pred in TBOX_PREDICATES:
        for subj, obj in g.subject_objects(pred):
            if is_domain_term(subj):
                tail = short(str(obj)) if isinstance(obj, URIRef) else str(obj)
                axioms.add(f"{short(str(subj))} {wk_qname(pred)} {tail}")
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
                "name": s.get("name", "?"), "uri": s.get("uri"),
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
            if str(anc) != c and str(anc) not in declared and is_domain_term(anc):
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
                   if str(d) not in declared and is_domain_term(d)}
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
    ontology_namespaces = {namespace(t) for t in declared}
    iris = [t for t in (referenced_data | referenced_query)
            if t not in declared_set and namespace(t) in ontology_namespaces]
    undeclared = []
    for t in sorted(iris, key=short):
        refs = [{"name": name, "uri": uri, "source_file": str(src) if src else None,
                 "in_data": t in sd, "in_query": t in sq}
                for (name, src, sd, sq, uri) in spec_refs if t in sd or t in sq]
        undeclared.append({"term": short(t), "iri": t, "refs": refs})
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

    # Machine-readable per-term records (full IRIs) for the RDF output — one per
    # declared term, with its role, where it's exercised, and the tests behind it.
    term_records = [{
        "iri": t, "slug": _slug(short(t)), "kind": declared[t],
        "role": _coverage_status(t, schema_only, used_data, used_query),
        "cq_role": _coverage_status(t, schema_only, cq_used_data, cq_used_query),
        "in_data": t in used_data, "in_query": t in used_query,
        "exercised_by": sorted({r["uri"] for r in test_refs.get(t, []) if r.get("uri")}),
    } for t in sorted(declared)]

    return {
        "covered": covered, "denominator": denominator,
        "pct": round(100.0 * covered / denominator) if denominator else 0,
        "ratio": (covered / denominator) if denominator else 0.0,
        "declared_total": len(declared), "schema_count": len(schema_only),
        "has_cq": bool(cq_defs),
        "covered_by_cq": covered_by_cq,
        "cq_pct": round(100.0 * covered_by_cq / denominator) if denominator else 0,
        "cq_ratio": (covered_by_cq / denominator) if denominator else 0.0,
        "terms": terms, "gaps": gaps, "cq_gaps": cq_gaps, "schema_terms": schema_terms,
        "undeclared": undeclared, "duplicate_cqs": duplicate_cqs,
        "tbox_in_data": _tbox_in_data(specs, short),
        "per_cq": per_cq, "term_records": term_records,
    }
