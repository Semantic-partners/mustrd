"""Rebuild the Coverage Report's template context from the coverage RDF graph.

The coverage graph (see `coverage_rdf.py`) is the canonical output of a run; the
Markdown Coverage Report is rendered *from it*. This module parses the graph
(plus the ontology graph, for the subClassOf tree) back into the dict the
existing jinja templates expect, so rendering is a pure function of the graph —
testable independently of how the graph was computed.

The CQ Report is still built from the compute dict (see the plugin); only the
`## Coverage Report` half comes through here for now.
"""
from rdflib import Namespace, RDF

from mustrd.ontology import shortener
from mustrd.coverage import _ordered_terms, _reason_key

COV = Namespace("https://mustrd.org/coverage/")
DQV = Namespace("http://www.w3.org/ns/dqv#")
MUST = Namespace("https://mustrd.org/model/")

_ROLE_STR = {COV.Covered: "covered", COV.QueryOnly: "query-only",
             COV.Structural: "schema", COV.Unused: "unused"}


def _bool(lit):
    return bool(lit.toPython()) if lit is not None else False


def _spec_meta(graph):
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
                              "in_data": _bool(graph.value(e, COV.inData)),
                              "in_query": _bool(graph.value(e, COV.inQuery))})
        facts[term] = {
            "role": _ROLE_STR[graph.value(tc, COV.role)],
            "cq_role": _ROLE_STR[cqr] if cqr is not None else "unused",
            "in_data": _bool(graph.value(tc, COV.inData)),
            "in_query": _bool(graph.value(tc, COV.inQuery)),
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
                         "in_data": _bool(graph.value(r, COV.inData)),
                         "in_query": _bool(graph.value(r, COV.inQuery))})
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


def coverage_context(graph, ontology_graph) -> dict:
    """The term-coverage slice of the report context, rebuilt from the graph."""
    short = shortener([ontology_graph])
    meta = _spec_meta(graph)
    facts, declared, reasons = _read_terms(graph, meta)

    terms = _ordered_terms(declared, facts, short, ontology_graph)

    schema_only = {t for t, f in facts.items() if f["role"] == "schema"}
    covered = sum(1 for f in facts.values() if f["role"] == "covered")
    covered_by_cq = sum(1 for f in facts.values() if f["cq_role"] == "covered")
    denominator = len(declared) - len(schema_only)
    has_cq = (None, DQV.isMeasurementOf, COV.termCoverageByCompetencyQuestions) in graph

    gaps = [{"term": short(t), "kind": declared[t],
             "query_only": facts[t]["role"] == "query-only"}
            for t in sorted(declared)
            if facts[t]["role"] in ("query-only", "unused")]
    schema_terms = [{"term": short(t), "kind": declared[t],
                     "reason": "; ".join(sorted(reasons[t], key=_reason_key)[:3])}
                    for t in sorted(declared) if t in schema_only]

    return {
        "covered": covered, "denominator": denominator,
        "pct": round(100.0 * covered / denominator) if denominator else 0,
        "declared_total": len(declared), "schema_count": len(schema_only),
        "has_cq": has_cq,
        "covered_by_cq": covered_by_cq,
        "cq_pct": round(100.0 * covered_by_cq / denominator) if denominator else 0,
        "terms": terms, "gaps": gaps, "schema_terms": schema_terms,
        "undeclared": _read_undeclared(graph, meta, short),
        "tbox_in_data": _read_tbox(graph, meta),
    }
