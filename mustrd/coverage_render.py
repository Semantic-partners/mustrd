"""Rebuild the Coverage Report's template context from the coverage RDF graph.

The coverage graph (see `coverage_rdf.py`) is the canonical output of a run; the
Markdown Coverage Report is rendered *from it*. This module parses the graph
(plus the ontology graph, for the subClassOf tree) back into the dict the
existing jinja templates expect, so rendering is a pure function of the graph —
testable independently of how the graph was computed.

The CQ Report is still built from the compute dict (see the plugin); only the
`## Coverage Report` half comes through here for now.
"""
from rdflib import RDF, URIRef
from rdflib.namespace import RDFS, OWL

from mustrd.namespace import COV, DQV, MUST
from mustrd.ontology import shortener, is_domain_term
from mustrd.coverage import reason_key, pct

_ROLE_STR = {COV.Covered: "covered", COV.QueryOnly: "query-only",
             COV.Structural: "schema", COV.Unused: "unused"}


def to_bool(lit):
    return bool(lit.toPython()) if lit is not None else False


def spec_meta(graph):
    """{spec IRI: {name, source_file}} from the spec metadata in the graph."""
    meta = {}
    for s in graph.subjects(RDF.type, MUST.TestSpec):
        src = graph.value(s, MUST.specSourceFile)
        meta[str(s)] = {"name": str(graph.value(s, MUST.specFileName) or s),
                        "source_file": str(src) if src is not None else None}
    return meta


def _read_terms(graph, meta):
    """Per-term facts + declared kinds + structural reasons, from the graph."""
    facts, declared, reasons = {}, {}, {}
    for tc in graph.subjects(RDF.type, COV.TermCoverage):
        term = str(graph.value(tc, COV["term"]))
        declared[term] = str(graph.value(tc, COV.kind))
        cqr = graph.value(tc, COV.cqRole)
        exercises = []
        for e in graph.objects(tc, COV.exercise):
            turi = str(graph.value(e, COV.test))
            m = meta.get(turi, {})
            exercises.append({"uri": turi, "name": m.get("name"),
                              "source_file": m.get("source_file"),
                              "in_data": to_bool(graph.value(e, COV.inData)),
                              "in_query": to_bool(graph.value(e, COV.inQuery))})
        facts[term] = {
            "role": _ROLE_STR[graph.value(tc, COV.role)],
            "cq_role": _ROLE_STR[cqr] if cqr is not None else "unused",
            "in_data": to_bool(graph.value(tc, COV.inData)),
            "in_query": to_bool(graph.value(tc, COV.inQuery)),
            "exercises": sorted(exercises, key=lambda r: r["name"] or ""),
        }
        reasons[term] = [str(x) for x in graph.objects(tc, COV.structuralReason)]
    return facts, declared, reasons


def _read_undeclared(graph, meta, short):
    out = []
    for issue in graph.subjects(COV.issueType, COV.UsedButNotDeclared):
        term = graph.value(issue, COV.aboutTerm)
        refs = []
        for r in graph.objects(issue, COV.reference):
            turi = str(graph.value(r, COV.test))
            refs.append({"name": meta.get(turi, {}).get("name"),
                         "source_file": meta.get(turi, {}).get("source_file"),
                         "in_data": to_bool(graph.value(r, COV.inData)),
                         "in_query": to_bool(graph.value(r, COV.inQuery))})
        out.append({"term": short(str(term)), "iri": str(term),
                    "refs": sorted(refs, key=lambda x: x["name"] or "")})
    return sorted(out, key=lambda u: u["term"])


def _read_tbox(graph, meta):
    out = []
    for issue in graph.subjects(COV.issueType, COV.TBoxInTestData):
        test = graph.value(issue, COV.aboutTest)
        m = meta.get(str(test), {}) if test is not None else {}
        out.append({"name": m.get("name"), "source_file": m.get("source_file"),
                    "axioms": sorted(str(a) for a in graph.objects(issue, COV.detail))})
    return sorted(out, key=lambda t: t["name"] or "")


def read_ontologies(graph):
    """The ontologies the run measured, from the graph — {uri, path, description}
    (the file link's href is computed by the caller). Sorted by IRI for a stable
    order (the graph has none)."""
    rows = []
    for s in graph.subjects(RDF.type, OWL.Ontology):   # not CQ nodes, which also carry cov:sourceFile
        src = graph.value(s, COV.sourceFile)
        desc = graph.value(s, RDFS.comment)
        rows.append({"uri": str(s),
                     "path": str(src) if src is not None else None,
                     "description": str(desc) if desc is not None else None})
    return sorted(rows, key=lambda r: r["uri"])


# --- term matrix (subClassOf tree) --------------------------------------------
# Presentation of the per-term facts as an indented subClassOf forest. Structure
# comes from the ontology graph (subClassOf/domain); every row's coverage data
# comes from the per-term `facts` map read back from the coverage graph.


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


def _matrix_row(term, kind, depth, connector, ctx, external=False):
    """One term's matrix row (columns + depth + connector), read from the per-term
    `facts` map. External (non-declared) terms have no facts and are structural.

    A fact is {role, cq_role, in_data, in_query, exercises: [{name, uri,
    source_file, in_data, in_query}]}. `exercises` lists every test behind the
    term (not just data ones) so a term whose data and SPARQL come from
    *different* tests is visible in its per-test sub-rows."""
    if external:
        return {"depth": depth, "kind": kind, "term": ctx["short"](term), "iri": term, "external": True,
                "connector": connector, "in_data": False, "in_query": False,
                "in_schema": True, "status": "schema", "cq_status": "schema",
                "by_cq_state": "schema"}
    f = ctx["facts"].get(term, {})
    role, cq_role = f.get("role", "unused"), f.get("cq_role", "unused")
    row = {"depth": depth, "kind": kind, "term": ctx["short"](term), "iri": term, "external": False,
           "connector": connector, "in_data": bool(f.get("in_data")),
           "in_query": bool(f.get("in_query")), "in_schema": role == "schema",
           "status": role, "cq_status": cq_role,
           "by_cq_state": "schema" if role == "schema" else ("yes" if cq_role == "covered" else "no")}
    if term in ctx["extra_parents"]:
        row["extra_parents"] = ctx["extra_parents"][term]
    if f.get("exercises"):
        row["cover_refs"] = f["exercises"]
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


def ordered_terms(declared, facts, short, tbox):
    """The per-term matrix as an ordered list of rows: an indented subClassOf
    tree of classes, each with its domain-attached properties (▸) beneath it;
    properties with no domain trail at the end.

    Structure comes from `declared` + `tbox` (subClassOf/domain); every row's
    coverage data comes from the per-term `facts` map."""
    referenced = {t for t, f in facts.items() if f.get("in_data") or f.get("in_query")}
    schema_only = {t for t, f in facts.items() if f.get("role") == "schema"}
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

    ctx = {"facts": facts, "schema_only": schema_only, "short": short,
           "external": external, "extra_parents": extra_parents}
    rows = []
    for root in roots:
        _walk_forest(root, 0, children, attached, ctx, rows)
    for p in unattached:
        rows.append(_matrix_row(p, "property", 0, None, ctx))
    return rows


def coverage_context(graph, ontology_graph) -> dict:
    """The term-coverage slice of the report context, rebuilt from the graph."""
    short = shortener([ontology_graph])
    meta = spec_meta(graph)
    facts, declared, reasons = _read_terms(graph, meta)

    terms = ordered_terms(declared, facts, short, ontology_graph)

    schema_only = {t for t, f in facts.items() if f["role"] == "schema"}
    covered = sum(1 for f in facts.values() if f["role"] == "covered")
    covered_by_cq = sum(1 for f in facts.values() if f["cq_role"] == "covered")
    denominator = len(declared) - len(schema_only)
    has_cq = (None, DQV.isMeasurementOf, COV.termCoverageByCompetencyQuestions) in graph

    gaps = [{"term": short(t), "iri": t, "kind": declared[t],
             "query_only": facts[t]["role"] == "query-only"}
            for t in sorted(declared)
            if facts[t]["role"] in ("query-only", "unused")]
    schema_terms = [{"term": short(t), "iri": t, "kind": declared[t],
                     "reason": "; ".join(sorted(reasons[t], key=reason_key)[:3])}
                    for t in sorted(declared) if t in schema_only]

    return {
        "covered": covered, "denominator": denominator,
        "pct": pct(covered, denominator),
        "declared_total": len(declared), "schema_count": len(schema_only),
        "has_cq": has_cq,
        "covered_by_cq": covered_by_cq,
        "cq_pct": pct(covered_by_cq, denominator),
        "terms": terms, "gaps": gaps, "schema_terms": schema_terms,
        "undeclared": _read_undeclared(graph, meta, short),
        "tbox_in_data": _read_tbox(graph, meta),
    }
