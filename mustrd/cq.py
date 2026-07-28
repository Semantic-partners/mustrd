"""Competency-question reporting.

Competency questions are first-class `cq:CompetencyQuestion` nodes (question +
optional `cq:cqSpec` links to the tests that answer them). This module turns the
collected CQ definitions into the report's CQ overlay and per-CQ breakdown; it
depends on the low-level term helpers in `mustrd.coverage` (one direction only —
coverage never imports this module at module load).

A **CQ definition** (built by the pytest plugin) is a dict:
    {id, name, question, questions, source_file, specs (linked spec dicts),
     missing_specs (unresolvable cqSpec IRIs)}
"""
from dataclasses import dataclass, field
from typing import List, Optional

from rdflib import Graph, URIRef

from mustrd.ontology import abox_terms, query_uris, is_domain_term
from mustrd.coverage import requires_ontology_terms


@dataclass
class SpecUsage:
    """One spec's contribution to a competency question."""
    name: str
    uri: Optional[str]
    passed: bool
    data_terms: List[str] = field(default_factory=list)
    query_terms: List[str] = field(default_factory=list)
    # Declared classes the query matches its data only *through* (subClassOf) —
    # their declaring ontology must be loaded for the test to pass. Empty = none.
    requires_ontology: List[str] = field(default_factory=list)


def _status(u: SpecUsage) -> str:
    return "passed" if u.passed else "not passed"


def _raw_terms(spec):
    """The domain-namespace IRIs a spec references, split (data, query) — raw
    (not yet intersected with the declared terms)."""
    g = spec.get("given")
    raw_data = abox_terms(g) if isinstance(g, Graph) else set()
    raw_query = set()
    for q in (spec.get("queries") or []):
        if isinstance(q, str):
            raw_query |= query_uris(q)
    return raw_data, raw_query


def _split_duplicate_cqs(cq_defs):
    """Partition CQ defs into (duplicate_cqs, kept).

    Two competency-question nodes sharing the same question text is almost always
    a copy/paste error, so every def carrying a duplicated question is dropped
    from the calculation. `duplicate_cqs` describes what was excluded, for a
    warning: [{question, cqs: [{name, source_file}, ...]}].
    """
    counts = {}
    for d in cq_defs:
        counts[d.get("question")] = counts.get(d.get("question"), 0) + 1
    dup_values = {q for q, n in counts.items() if q is not None and n > 1}
    kept = [d for d in cq_defs if d.get("question") not in dup_values]
    duplicate_cqs = [{
        "question": q,
        "cqs": [{"id": d.get("id"), "name": d.get("name", "?"),
                 "questions": d.get("questions", []),
                 "source_file": str(d.get("source_file")) if d.get("source_file") else None}
                for d in cq_defs if d.get("question") == q],
    } for q in sorted(dup_values)]
    return duplicate_cqs, kept


def _linked_specs(cq_defs):
    """Deduped list of the spec dicts linked (via cq:cqSpec) by any CQ def."""
    seen, out = set(), []
    for d in cq_defs:
        for s in d.get("specs", []):
            key = s.get("uri") or id(s)
            if key not in seen:
                seen.add(key)
                out.append(s)
    return out


def _per_cq_entries(cq_defs, usage_by_uri):
    """One report entry per CQ node: its question, the linked test(s) with their
    status/terms, and the two error flags (multiple questions, dangling cqSpec).
    A CQ with no (resolvable) test gets has_test=False and empty terms."""
    entries = []
    for d in cq_defs:
        tests, data, query, credited = [], set(), set(), False
        for s in d.get("specs", []):
            u = usage_by_uri.get(s.get("uri"))
            if u is None:
                continue
            tests.append({"name": u.name, "uri": u.uri, "status": _status(u),
                          "credited": u.passed,
                          "requires_ontology_terms": u.requires_ontology})
            data.update(u.data_terms)
            query.update(u.query_terms)
            credited = credited or u.passed
        entries.append({
            "id": d.get("id"), "name": d.get("name"),
            "source_file": d.get("source_file"),
            "question": d.get("question"), "questions": d.get("questions", []),
            "question_error": len(d.get("questions", [])) > 1,
            "missing_specs": d.get("missing_specs", []),
            "has_test": bool(tests), "tests": tests,
            "data": sorted(data), "query": sorted(query), "credited": credited,
        })
    return entries


def compute_cq_overlay(cq_defs, declared_set, declared, tbox, short):
    """The CQ overlay for term coverage: which declared terms competency questions
    exercise (deduped), the per-CQ breakdown, and the duplicate-question warning.
    """
    duplicate_cqs, kept = _split_duplicate_cqs(cq_defs or [])
    linked = _linked_specs(kept)
    usage_by_uri, cq_used_data, cq_used_query = {}, set(), set()
    for s in linked:
        raw_data, raw_query = _raw_terms(s)
        d_terms = raw_data & declared_set
        q_terms = raw_query & declared_set
        usage_by_uri[s.get("uri")] = SpecUsage(
            name=s.get("name", "?"), uri=s.get("uri"), passed=bool(s.get("passed")),
            data_terms=sorted(short(t) for t in d_terms),
            query_terms=sorted(short(t) for t in q_terms),
            requires_ontology=requires_ontology_terms(d_terms, q_terms, declared, tbox))
        if s.get("passed"):
            cq_used_data |= d_terms
            cq_used_query |= q_terms
    return {
        "cq_used_data": cq_used_data, "cq_used_query": cq_used_query,
        "per_cq": _per_cq_entries(kept, usage_by_uri),
        "duplicate_cqs": duplicate_cqs,
    }


def cq_facts(cq_defs: List[dict]) -> dict:
    """The facts for a CQ-only RDF graph (for `--cq` with no ontology).

    Returns {per_cq, duplicate_cqs, spec_usage, prefixes}: the per-CQ breakdown
    (test statuses; requires-ontology is n/a without a TBox), each linked spec's
    domain-term usage (declared or not — nothing to check against), and the
    domain namespace prefixes to bind into the graph so the renderer can shorten
    term IRIs. The graph builder is `coverage_rdf.cq_graph`.
    """
    duplicate_cqs, kept = _split_duplicate_cqs(cq_defs or [])
    linked = _linked_specs(kept)
    usage_by_uri, spec_usage, prefixes = {}, {}, {}
    for s in linked:
        raw_data, raw_query = _raw_terms(s)
        d = sorted(t for t in raw_data if is_domain_term(URIRef(t)))
        q = sorted(t for t in raw_query if is_domain_term(URIRef(t)))
        uri = s.get("uri")
        spec_usage[uri] = {
            "name": s.get("name", "?"),
            "source_file": str(s.get("source_file")) if s.get("source_file") else None,
            "data": d, "query": q}
        usage_by_uri[uri] = SpecUsage(name=s.get("name", "?"), uri=uri,
                                      passed=bool(s.get("passed")), requires_ontology=[])
        g = s.get("given")
        if isinstance(g, Graph):
            for prefix, ns in g.namespaces():
                if prefix:
                    prefixes[prefix] = str(ns)
    return {"per_cq": _per_cq_entries(kept, usage_by_uri),
            "duplicate_cqs": duplicate_cqs, "spec_usage": spec_usage,
            "prefixes": prefixes}
