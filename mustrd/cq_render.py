"""Rebuild the Competency Questions report from the coverage RDF graph.

Mirrors `coverage_render` for the CQ half: the CQ nodes, their `cov:Assertion`s,
per-spec `cov:usesInData/usesInQuery`, and (when an ontology was checked) the
per-term `cov:cqRole` are read back into the dicts the existing CQ templates
expect. Works with or without an ontology (a CQ-only graph has no
`cov:TermCoverage`, so `declared` is empty and there is no CQ-gap section).
"""
from rdflib import Namespace, RDF

from mustrd.ontology import shortener
from mustrd.coverage_render import _spec_meta, _bool

COV = Namespace("https://mustrd.org/coverage/")
CQ = Namespace("https://mustrd.org/competencyQuestion/")


def _local(iri):
    s = str(iri)
    for sep in ("#", "/"):
        if sep in s:
            s = s.rsplit(sep, 1)[-1]
    return s or str(iri)


def _spec_usage(graph):
    """{spec IRI: {data: [term IRIs], query: [term IRIs]}} from cov:usesIn*."""
    usage = {}
    for s in set(graph.subjects(COV.usesInData, None)) | set(graph.subjects(COV.usesInQuery, None)):
        usage[str(s)] = {"data": [str(t) for t in graph.objects(s, COV.usesInData)],
                         "query": [str(t) for t in graph.objects(s, COV.usesInQuery)]}
    return usage


def _assertions(graph):
    """{(cq IRI, test IRI): {status, requires_ontology}} from the cov:Assertions."""
    out = {}
    for a in graph.subjects(RDF.type, COV.Assertion):
        cq = graph.value(a, COV.onCompetencyQuestion)
        test = graph.value(a, COV.onTest)
        if cq is None or test is None:
            continue
        out[(str(cq), str(test))] = {
            "status": "passed" if graph.value(a, COV.outcome) == COV.Passed else "not passed",
            "requires_ontology": _bool(graph.value(a, COV.requiresOntology))}
    return out


def _undeclared_by_spec(graph, short):
    """{test IRI: ["term (where)", ...]} from the used-but-not-declared issues."""
    out = {}
    for issue in graph.subjects(COV.issueType, COV.UsedButNotDeclared):
        term = short(str(graph.value(issue, COV.aboutTerm)))
        for r in graph.objects(issue, COV.reference):
            test = graph.value(r, COV.test)
            if test is None:
                continue
            in_d, in_q = _bool(graph.value(r, COV.inData)), _bool(graph.value(r, COV.inQuery))
            where = "data & SPARQL" if in_d and in_q else "input data" if in_d else "SPARQL"
            out.setdefault(str(test), []).append(f"{term} ({where})")
    return out


def _cq_specs(graph):
    return {str(o) for cq in graph.subjects(RDF.type, CQ.CompetencyQuestion)
            for o in graph.objects(cq, CQ.cqSpec)}


def _one_cq(graph, cq, meta, usage, assertions, undeclared, declared, short, href, has_ontology):
    questions = sorted(str(q) for q in graph.objects(cq, CQ.question))
    specs = [str(o) for o in graph.objects(cq, CQ.cqSpec)]
    tests, missing = [], []
    for su in sorted(specs):
        if su not in meta:                       # dangling cqSpec -> missing test
            missing.append(su)
            continue
        a = assertions.get((str(cq), su), {})
        cov_status = None
        if has_ontology:
            probs = sorted(undeclared.get(su, []))
            cov_status = ("⚠️ undeclared: " + "; ".join(probs)) if probs else "✅ passed"
        tests.append({"name": meta[su]["name"], "uri": su,
                      "status": a.get("status", "not passed"),
                      "credited": a.get("status") == "passed",
                      "requires_ontology": a.get("requires_ontology", False),
                      "test_link": href(meta[su].get("source_file")),
                      "coverage_status": cov_status})
    data, query = set(), set()
    for su in specs:
        u = usage.get(su, {})
        data |= set(u.get("data", []))
        query |= set(u.get("query", []))
    if declared:                                 # with an ontology, declared only
        data &= declared
        query &= declared
    return {"id": str(cq), "name": _local(cq),
            "question": questions[0] if questions else None, "questions": questions,
            "question_error": len(questions) > 1,
            "missing_specs": missing, "missing_names": [_local(m) for m in missing],
            "has_test": bool(tests), "tests": sorted(tests, key=lambda t: t["name"] or ""),
            "data": sorted(short(t) for t in data),
            "query": sorted(short(t) for t in query),
            "credited": any(t["credited"] for t in tests)}


def _duplicate_cqs(graph, href):
    groups = {}
    for cq in graph.subjects(COV.duplicate, None):
        if not _bool(graph.value(cq, COV.duplicate)):
            continue
        q = graph.value(cq, CQ.question)
        src = graph.value(cq, COV.sourceFile)
        groups.setdefault(str(q) if q is not None else "", []).append(
            {"name": _local(cq), "link": href(str(src)) if src is not None else None})
    return [{"question": q, "cqs": sorted(cqs, key=lambda c: c["name"])}
            for q, cqs in sorted(groups.items())]


def _cq_gaps(graph, declared, cq_specs, meta, short, href):
    """Declared, non-structural terms no competency question covers in data;
    naming the non-CQ test(s) that do (from the term's cov:Exercise records)."""
    gaps = []
    for tc in graph.subjects(RDF.type, COV.TermCoverage):
        cq_role = graph.value(tc, COV.cqRole)
        if cq_role in (COV.Covered, COV.Structural, None):
            continue
        term = str(graph.value(tc, COV["term"]))
        refs = []
        for ex in graph.objects(tc, COV.exercise):
            test = str(graph.value(ex, COV.test))
            if test in cq_specs:
                continue
            refs.append({"name": meta.get(test, {}).get("name"),
                         "link": href(meta.get(test, {}).get("source_file")),
                         "in_data": _bool(graph.value(ex, COV.inData)),
                         "in_query": _bool(graph.value(ex, COV.inQuery))})
        entry = {"term": short(term), "iri": term,
                 "kind": str(graph.value(tc, COV.kind)),
                 "query_only": cq_role == COV.QueryOnly}
        if refs:
            entry["non_cq_refs"] = sorted(refs, key=lambda r: r["name"] or "")
        gaps.append(entry)
    return sorted(gaps, key=lambda g: g["term"])


def cq_report(graph, ontology_graph, href) -> dict:
    """The CQ-report context: {per_cq, duplicate_cqs, cq_gaps, has_ontology}."""
    has_ontology = ontology_graph is not None
    short = shortener([ontology_graph] if has_ontology else [graph])
    meta = _spec_meta(graph)
    usage = _spec_usage(graph)
    assertions = _assertions(graph)
    undeclared = _undeclared_by_spec(graph, short)
    declared = {str(graph.value(tc, COV["term"]))
                for tc in graph.subjects(RDF.type, COV.TermCoverage)}
    cq_specs = _cq_specs(graph)

    per_cq = [_one_cq(graph, cq, meta, usage, assertions, undeclared, declared,
                      short, href, has_ontology)
              for cq in graph.subjects(RDF.type, CQ.CompetencyQuestion)
              if not _bool(graph.value(cq, COV.duplicate))]
    per_cq.sort(key=lambda e: (e["question"] or "", e["name"]))

    return {"per_cq": per_cq,
            "duplicate_cqs": _duplicate_cqs(graph, href),
            "cq_gaps": _cq_gaps(graph, declared, cq_specs, meta, short, href) if has_ontology else [],
            "has_ontology": has_ontology}
