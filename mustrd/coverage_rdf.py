"""Render a coverage result as RDF (W3C DQV + PROV), for a knowledge graph.

Turns the dict `compute_coverage` produces into a graph that can be merged into a
triplestore and queried: DQV quality measurements (term coverage, as a decimal
ratio) `dqv:computedOn` the ontology IRI(s) and their `owl:versionIRI`, plus a
`cov:TermCoverage` record per declared term (its role, where it's exercised, and
the tests behind it) and `cov:QualityIssue`s for the signals. All instances get
stable minted IRIs — no blank nodes — so successive runs merge and diff cleanly.
The vocabulary is `mustrd/model/coverage-ontology.ttl`.
"""
import os

from rdflib import Graph, URIRef, Literal, RDF, RDFS, OWL, XSD
from rdflib.namespace import SKOS

from mustrd.namespace import MUST, CQ, COV, DQV, PROV
from mustrd.ontology import local_name, slug

_BASE = "https://mustrd.org/coverage/"
_AGENT = URIRef("https://mustrd.org/#tool")
_ROLE = {"covered": COV.Covered, "query-only": COV.QueryOnly,
         "schema": COV.Structural, "unused": COV.Unused}


def _relpath(p):
    # forward slashes so stored paths are OS-independent (they surface as report
    # links, and the graph must be identical whatever platform generated it)
    try:
        return os.path.relpath(str(p)).replace(os.sep, "/")
    except ValueError:
        return str(p).replace(os.sep, "/")


def _local(iri) -> str:
    """A slugged local name, for minting a stable IRI segment from a term/IRI."""
    return slug(local_name(iri))


def _run_provenance(g, run, prov):
    """When it ran (prov:startedAtTime), the source repo (cov:gitRepository), the
    revision (cov:gitCommit SHA + cov:gitCommitUrl link), and the CI job
    (cov:ciRun) — each emitted only when known."""
    if prov.get("started"):
        g.add((run, PROV.startedAtTime, Literal(prov["started"], datatype=XSD.dateTime)))
    if prov.get("repo_url"):
        g.add((run, COV.gitRepository, URIRef(prov["repo_url"])))
    if prov.get("git_sha"):
        g.add((run, COV.gitCommit, Literal(prov["git_sha"])))
    if prov.get("commit_url"):
        g.add((run, COV.gitCommitUrl, URIRef(prov["commit_url"])))
    if prov.get("ci_run"):
        g.add((run, COV.ciRun, URIRef(prov["ci_run"])))


def _add_provenance(g, run, ontologies, prov, mustrd_version):
    """The run + agent, the run's provenance (when it ran, the revision, the CI
    job), and the ontology IRIs (+ owl:versionIRI) the coverage is about. `prov`
    is {git_sha, started, commit_url, ci_run}. Returns the `dqv:computedOn`
    subjects (ontologies and their versions)."""
    g.add((run, RDF.type, COV.CoverageRun))
    g.add((_AGENT, RDF.type, PROV.SoftwareAgent))
    g.add((_AGENT, RDFS.label, Literal("mustrd")))
    if mustrd_version:
        g.add((_AGENT, OWL.versionInfo, Literal(mustrd_version)))
    g.add((run, PROV.wasAssociatedWith, _AGENT))
    _run_provenance(g, run, prov)
    subjects = []
    for o in ontologies:
        if not o.get("uri"):
            continue
        uri = URIRef(o["uri"])
        subjects.append(uri)
        g.add((run, PROV.used, uri))
        g.add((uri, RDF.type, OWL.Ontology))
        if o.get("path"):
            g.add((uri, COV.sourceFile, Literal(_relpath(o["path"]))))
        if o.get("description"):
            g.add((uri, RDFS.comment, Literal(o["description"])))
        if o.get("version"):
            ver = URIRef(o["version"])
            subjects.append(ver)
            g.add((uri, OWL.versionIRI, ver))
    return subjects


def _add_measurements(g, run, run_slug, subjects, coverage):
    def measurement(local, metric, ratio):
        m = URIRef(f"{_BASE}run/{run_slug}/measurement/{local}")
        g.add((m, RDF.type, DQV.QualityMeasurement))
        g.add((m, DQV.isMeasurementOf, metric))
        g.add((m, DQV.value, Literal(round(ratio, 4), datatype=XSD.decimal)))
        g.add((m, PROV.wasGeneratedBy, run))
        for s in subjects:
            g.add((m, DQV.computedOn, s))

    measurement("termCoverageByTests", COV.termCoverageByTests,
                coverage.get("ratio", 0.0))
    if coverage.get("has_cq"):
        measurement("termCoverageByCompetencyQuestions",
                    COV.termCoverageByCompetencyQuestions, coverage.get("cq_ratio", 0.0))


def _add_term_records(g, run, run_slug, coverage):
    has_cq = coverage.get("has_cq")
    for rec in coverage.get("term_records", []):
        tc = URIRef(f"{_BASE}run/{run_slug}/term/{rec['slug']}")
        g.add((tc, RDF.type, COV.TermCoverage))
        g.add((tc, COV["term"], URIRef(rec["iri"])))   # COV.term is Namespace.term()
        g.add((tc, COV.kind, Literal(rec["kind"])))
        g.add((tc, COV.role, _ROLE[rec["role"]]))
        g.add((tc, COV.inData, Literal(bool(rec["in_data"]))))
        g.add((tc, COV.inQuery, Literal(bool(rec["in_query"]))))
        g.add((tc, PROV.wasGeneratedBy, run))
        if has_cq:
            g.add((tc, COV.cqRole, _ROLE[rec["cq_role"]]))
        for reason in rec.get("structural_reasons", []):
            g.add((tc, COV.structuralReason, Literal(reason)))
        for ex in rec.get("exercises", []):
            if not ex.get("uri"):
                continue
            e = URIRef(f"{tc}/by/{_local(ex['uri'])}")
            g.add((tc, COV.exercise, e))
            g.add((e, RDF.type, COV.Exercise))
            g.add((e, COV.test, URIRef(ex["uri"])))
            g.add((e, COV.inData, Literal(bool(ex.get("in_data")))))
            g.add((e, COV.inQuery, Literal(bool(ex.get("in_query")))))


def _add_issues(g, run, run_slug, coverage):
    for u in coverage.get("undeclared", []):
        if not u.get("iri"):
            continue
        issue = URIRef(f"{_BASE}run/{run_slug}/issue/used-but-not-declared/{_local(u['iri'])}")
        g.add((issue, RDF.type, COV.QualityIssue))
        g.add((issue, COV.issueType, COV.UsedButNotDeclared))
        g.add((issue, COV.aboutTerm, URIRef(u["iri"])))
        g.add((issue, PROV.wasGeneratedBy, run))
        for r in u.get("refs", []):
            if not r.get("uri"):
                continue
            g.add((issue, COV.aboutTest, URIRef(r["uri"])))
            ref = URIRef(f"{issue}/by/{_local(r['uri'])}")
            g.add((issue, COV.reference, ref))
            g.add((ref, RDF.type, COV.Reference))
            g.add((ref, COV.test, URIRef(r["uri"])))
            g.add((ref, COV.inData, Literal(bool(r.get("in_data")))))
            g.add((ref, COV.inQuery, Literal(bool(r.get("in_query")))))

    for t in coverage.get("tbox_in_data", []):
        issue = URIRef(f"{_BASE}run/{run_slug}/issue/tbox-in-data/"
                       f"{_local(t.get('uri') or t.get('name', '?'))}")
        g.add((issue, RDF.type, COV.QualityIssue))
        g.add((issue, COV.issueType, COV.TBoxInTestData))
        g.add((issue, PROV.wasGeneratedBy, run))
        if t.get("uri"):
            g.add((issue, COV.aboutTest, URIRef(t["uri"])))
        for ax in t.get("axioms", []):
            g.add((issue, COV.detail, Literal(ax)))


def _add_spec_metadata(g, coverage):
    """Emit each test spec's file name + (cwd-relative) source path and its
    domain-term usage (cov:usesInData/usesInQuery), so the renderer can label and
    link tests and rebuild per-CQ term lists straight from the graph."""
    for uri, u in sorted(coverage.get("spec_usage", {}).items()):
        s = URIRef(uri)
        g.add((s, RDF.type, MUST.TestSpec))
        if u.get("name"):
            g.add((s, MUST.specFileName, Literal(u["name"])))
        if u.get("source_file"):
            g.add((s, MUST.specSourceFile, Literal(_relpath(u["source_file"]))))
        for t in u.get("data", []):
            g.add((s, COV.usesInData, URIRef(t)))
        for t in u.get("query", []):
            g.add((s, COV.usesInQuery, URIRef(t)))


def _ontology_for_term(term, term_ontology, ont_uris):
    """The run ontology IRI that declares `term`. Authoritative: the term->ontology
    map (built from actual declarations). Falls back to the longest ontology IRI
    that lexically prefixes the term only when the map has no entry (e.g. a
    directly-constructed graph with no ontology files behind it)."""
    if term in term_ontology:
        return term_ontology[term]
    matches = [u for u in ont_uris if term.startswith(u)]
    return max(matches, key=len) if matches else None


def _add_cq_assertions(g, run, cq, tests, term_ontology, ont_uris):
    for t in tests:
        if not t.get("uri"):
            continue
        spec = URIRef(t["uri"])
        g.add((cq, CQ.cqSpec, spec))
        a = URIRef(f"{run}/assertion/{_local(cq)}/{_local(t['uri'])}")
        g.add((a, RDF.type, COV.Assertion))
        g.add((a, COV.onCompetencyQuestion, cq))
        g.add((a, COV.onTest, spec))
        g.add((a, COV.outcome, COV.Passed if t.get("status") == "passed" else COV.Failed))
        # cov:requiresOntology -> the ontology IRI(s) whose class hierarchy the test
        # matches its data through (was a boolean). One per driving declared class,
        # resolved to its declaring ontology; falls back to all run ontologies if a
        # term can't be matched, so the "requires ontology" signal is never lost.
        for term in t.get("requires_ontology_terms", []):
            matched = _ontology_for_term(term, term_ontology, ont_uris)
            for ont in ([matched] if matched else ont_uris):
                g.add((a, COV.requiresOntology, URIRef(ont)))
        g.add((a, PROV.wasGeneratedBy, run))


def _add_competency_questions(g, run, per_cq, duplicate_cqs,
                              term_ontology=None, ont_uris=()):
    """Emit each CQ node (cq:CompetencyQuestion + cq:question + cq:cqSpec) and,
    per linked test, a cov:Assertion carrying the outcome and any
    cov:requiresOntology links. Duplicate-question CQs link to their peers with
    cov:duplicateOf."""
    for e in per_cq:
        if not e.get("id"):
            continue
        cq = URIRef(e["id"])
        g.add((cq, RDF.type, CQ.CompetencyQuestion))
        for q in e.get("questions", []):
            g.add((cq, CQ.question, Literal(q)))
        if e.get("source_file"):
            g.add((cq, COV.sourceFile, Literal(_relpath(e["source_file"]))))
        g.add((cq, PROV.wasGeneratedBy, run))
        _add_cq_assertions(g, run, cq, e.get("tests", []), term_ontology or {}, ont_uris)
        for m in e.get("missing_specs", []):
            g.add((cq, CQ.cqSpec, URIRef(m)))   # dangling: no spec metadata -> flagged
    _add_duplicate_cqs(g, run, duplicate_cqs)


def _add_duplicate_cqs(g, run, duplicate_cqs):
    """Each duplicate CQ node, plus a run-scoped cov:Assertion recording that it
    duplicates its peer(s) — cov:duplicateOf lives on the assertion, not the CQ,
    so the CQ node stays free of run findings."""
    for d in duplicate_cqs:
        members = [c for c in d.get("cqs", []) if c.get("id")]
        for c in members:
            cq = URIRef(c["id"])
            g.add((cq, RDF.type, CQ.CompetencyQuestion))
            for q in (c.get("questions") or [d["question"]]):
                g.add((cq, CQ.question, Literal(q)))
            if c.get("source_file"):
                g.add((cq, COV.sourceFile, Literal(_relpath(c["source_file"]))))
            peers = [URIRef(o["id"]) for o in members if o["id"] != c["id"]]
            if peers:
                a = URIRef(f"{run}/assertion/duplicate/{_local(cq)}")
                g.add((a, RDF.type, COV.Assertion))
                g.add((a, COV.onCompetencyQuestion, cq))
                for peer in peers:                      # symmetric across the group
                    g.add((a, COV.duplicateOf, peer))
                g.add((a, PROV.wasGeneratedBy, run))


def _bind_prefixes(g, extra=()):
    for p, ns in (("cov", COV), ("dqv", DQV), ("prov", PROV), ("must", MUST),
                  ("cq", CQ), ("skos", SKOS), ("owl", OWL)):
        g.bind(p, ns)
    for prefix, ns in extra:
        g.bind(prefix, ns)


def coverage_graph(coverage, ontologies, run_slug="local", git_sha=None,
                   repo_url=None, started=None, commit_url=None, ci_run=None,
                   mustrd_version=None, term_ontology=None) -> Graph:
    """Build the RDF graph. `ontologies` is [{uri, version}] (uri required);
    `run_slug` seeds the minted run IRI (unique per run, see plugin._run_ident).
    The provenance kwargs (git_sha/started/commit_url/ci_run) describe the run.
    `term_ontology` maps term IRI -> its declaring owl:Ontology IRI (see
    `ontology.term_ontology_index`) — used to link cov:requiresOntology to the
    right ontology; falls back to a namespace-prefix guess when absent."""
    g = Graph()
    _bind_prefixes(g)
    run = URIRef(f"{_BASE}run/{run_slug}")
    prov = {"git_sha": git_sha, "repo_url": repo_url, "started": started,
            "commit_url": commit_url, "ci_run": ci_run}
    subjects = _add_provenance(g, run, ontologies, prov, mustrd_version)
    _add_measurements(g, run, run_slug, subjects, coverage)
    _add_term_records(g, run, run_slug, coverage)
    _add_issues(g, run, run_slug, coverage)
    _add_spec_metadata(g, coverage)
    ont_uris = [o["uri"] for o in ontologies if o.get("uri")]
    _add_competency_questions(g, run, coverage.get("per_cq", []),
                              coverage.get("duplicate_cqs", []),
                              term_ontology or {}, ont_uris)
    return g


def cq_graph(cq_facts, run_slug="local", git_sha=None, repo_url=None, started=None,
             commit_url=None, ci_run=None, mustrd_version=None) -> Graph:
    """A CQ-only graph for `--cq` with no ontology: CQ nodes + assertions + per-spec
    term usage, no coverage measurements. `cq_facts` (from `cq.cq_facts`) carries
    per_cq, duplicate_cqs, spec_usage and the domain prefixes to bind (so the
    renderer can shorten term IRIs without the ontology)."""
    g = Graph()
    _bind_prefixes(g, extra=cq_facts.get("prefixes", {}).items())
    run = URIRef(f"{_BASE}run/{run_slug}")
    prov = {"git_sha": git_sha, "repo_url": repo_url, "started": started,
            "commit_url": commit_url, "ci_run": ci_run}
    _add_provenance(g, run, [], prov, mustrd_version)
    _add_spec_metadata(g, cq_facts)
    _add_competency_questions(g, run, cq_facts.get("per_cq", []),
                              cq_facts.get("duplicate_cqs", []))
    return g
