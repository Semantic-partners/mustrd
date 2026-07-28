"""Render a run's per-test results as RDF, for the standalone results viewer.

Where `coverage_rdf.py` records what a run found about an *ontology* (term
coverage) and about *competency questions* (cov:Assertion, CQ-linked only), this
records the plain fact every test reporter has: each collected test's outcome.
Emitted for ALL tests (mustrd specs and plain pytest tests), three-valued
(passed / failed / skipped), with timing and the module/class/name grouping the
Playwright-style tree needs.

The graph shares the run IRI and cov:/must: vocabulary with the coverage graph,
so the two merge cleanly (stable minted IRIs, no blank nodes) — the viewer can
load them together or apart.
"""
from dataclasses import dataclass

from rdflib import Graph, URIRef, Literal, RDF, XSD

from mustrd.coverage_rdf import COV, PROV, MUST, _BASE, _relpath, _add_provenance
from mustrd.ontology import slug

_OUTCOME = {"passed": COV.Passed, "failed": COV.Failed, "skipped": COV.Skipped}


@dataclass
class RunResult:
    """One test's execution outcome in a run — the plain-data record both the
    pytest plugin and the CLI build, and the input to results_graph()."""
    status: str                 # "passed" | "failed" | "skipped"
    test_type: str              # "mustrd" | "pytest"
    module: str
    class_name: str
    test_name: str
    spec_uri: str = None        # the must:TestSpec IRI, when it is a mustrd spec
    spec_file_name: str = None
    source_file: str = None
    duration: float = None      # wall-clock seconds


def results_graph(run_results, run_slug="local", git_sha=None, repo_url=None,
                  started=None, commit_url=None, ci_run=None,
                  mustrd_version=None) -> Graph:
    """Build the per-test results graph for a run. `run_results` is a list of
    RunResult. `run_slug` seeds the (shared) run IRI.

    Takes the same run provenance as coverage_graph and asserts it through the
    same helper, so a results-only graph (--results-rdf with no ontology) still
    says when it ran and at what revision — and so a merge with the coverage graph
    contributes identical triples about the same run rather than a second opinion.
    """
    g = Graph()
    for p, ns in (("cov", COV), ("prov", PROV), ("must", MUST)):
        g.bind(p, ns)
    run = URIRef(f"{_BASE}run/{run_slug}")
    _add_provenance(g, run, [], {"git_sha": git_sha, "repo_url": repo_url,
                                 "started": started, "commit_url": commit_url,
                                 "ci_run": ci_run}, mustrd_version)

    seen = {}
    for i, r in enumerate(run_results):
        # A stable per-result IRI: by spec (+ triple-store-bearing test name) when
        # there is one, else by index — enough to keep successive runs mergeable.
        key = slug(f"{r.spec_uri or ''}-{r.test_name}") or str(i)
        if key in seen:
            key = f"{key}-{i}"
        seen[key] = True
        res = URIRef(f"{_BASE}run/{run_slug}/result/{key}")

        g.add((res, RDF.type, COV.TestResult))
        g.add((res, COV.resultOutcome, _OUTCOME.get(r.status, COV.Failed)))
        g.add((res, COV.testType, Literal(r.test_type)))
        if r.module:
            g.add((res, COV.module, Literal(r.module)))
        if r.class_name:
            g.add((res, COV.className, Literal(r.class_name)))
        if r.test_name:
            g.add((res, COV.testName, Literal(r.test_name)))
        if r.duration is not None:
            g.add((res, COV.duration, Literal(round(float(r.duration), 4),
                                              datatype=XSD.decimal)))
        g.add((res, PROV.wasGeneratedBy, run))

        if r.spec_uri:
            spec = URIRef(r.spec_uri)
            g.add((res, COV.resultTest, spec))
            g.add((spec, RDF.type, MUST.TestSpec))
            # Carry the spec's own metadata so the results graph is legible when
            # loaded on its own (idempotent with the coverage graph's copy).
            if r.spec_file_name:
                g.add((spec, MUST.specFileName, Literal(r.spec_file_name)))
            if r.source_file:
                g.add((spec, MUST.specSourceFile, Literal(_relpath(r.source_file))))
        elif r.source_file:
            g.add((res, COV.sourceFile, Literal(_relpath(r.source_file))))

    return g


def write_results_rdf(run_results, path, fmt="turtle", **run_ident) -> None:
    results_graph(run_results, **run_ident).serialize(destination=str(path), format=fmt)
