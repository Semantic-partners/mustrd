# Ontology term coverage

**Status:** Implemented (draft PR).

Two independent, opt-in flags:

- **`--term-coverage`** — ontology term coverage over **all mustrd tests**. It
  needs an ontology (`:hasOntologyPath`) and produces:
  1. **Ontologies** — the files measured against, as clickable links (relative to
     the report so they render in a Markdown previewer — or absolute GitHub URLs
     when running as a GitHub Action, see *Report links* below), each with the
     `owl:Ontology` IRI and description;
  2. **Ontology term coverage** — the percentage and a per-term matrix. Class
     rows are arranged as a `rdfs:subClassOf` **tree** (indented under their
     superclass); each class's properties sit beneath it (`▸`, by
     `rdfs:domain`). An *external* superclass or domain (e.g. `foaf:Person`)
     appears as its own structural row, and a linear run of structural-only ancestors
     collapses into a single grouped row (a property on an ancestor keeps it
     visible). Then the structural terms, the terms
     **not used by any test**, and any terms a test references that are *not*
     declared (likely typos / missing definitions).
- **`--cq`** — competency-question sections: a **Competency Questions** table and
  a **Per competency question** breakdown. Needs no ontology and can be used on
  its own.

A competency question is a first-class **`cq:CompetencyQuestion`** node — its
vocabulary lives in its own ontology (`mustrd/model/cq-ontology.ttl`, prefix
`cq:` = `https://mustrd.org/competencyQuestion/`). `cq:question` (a sub-property
of `rdfs:label`, exactly one) holds the text, and `cq:cqSpec` optionally links
the mustrd test(s) that answer it. CQ nodes are discovered in any `.mustrd.ttl`
under the suite's `hasSpecPath`. Because the link
is optional, a CQ can be recorded before its test exists; the table lists such
CQs with an em-dash Test cell. The table also flags a CQ with more than one
`cq:question` and a `cq:cqSpec` pointing at a non-existent spec.

The flags **compose**. With both, coverage gains a CQ overlay: a second headline
percentage (how much of the ontology the *competency questions* cover, vs all
tests), a **CQ Term Coverage** column per term, a second **Not used by any CQ** gap list
(CQ-scoped, alongside the all-tests one), a Coverage Status column in the CQ
table, and — because a duplicated `cq:question` is usually a copy/paste slip —
those CQ nodes are excluded from the CQ overlay and listed under a *Duplicate
competency questions* warning.

It is printed to **stdout**; adding `--md` also writes it to the report file
The report is printed to **stdout**; adding `--md` also writes it to the file
(creating the parent directory if needed). With **neither** flag, `--md` is
unchanged — it writes the standard test-results summary (a `ResultList` of every
test), no ontology required.

The ontology to measure against is named in the test configuration with
`mustrdTest:hasOntologyPath`. The value is a path (relative to the config file)
to **a file or a directory**; a directory is scanned **recursively** for RDF
files. The property may be **repeated** for multiple ontologies:

```ttl
:myTest a :MustrdTest ;
    :hasSpecPath     "specs/" ;
    :hasDataPath     "data/" ;
    :hasOntologyPath "ontology/" ,           # a directory (scanned recursively)
                     "vocab/extra.ttl" ;     # or an individual file
    :filterOnTripleStore triplestore:RdfLib .
```

```bash
# ontology coverage over all tests, to stdout
pytest --mustrd --config=config.ttl --term-coverage

# coverage + competency-question sections, written to a report file
pytest --mustrd --config=config.ttl --term-coverage --cq --md=report.md

# competency-question table only (no ontology needed)
pytest --mustrd --config=config.ttl --cq --md=report.md
```

If `--term-coverage` is given but no `hasOntologyPath` is set, mustrd **fails
early** (before running tests) with the config file to amend and a proposed
triple. Without `--term-coverage`, no coverage is computed and no ontology is
required; `--md` on its own writes the standard test-results summary, exactly as
before this feature.

## Motivation

The CQ table answers *"which competency questions have a passing test?"* — one
row per `cq:CompetencyQuestion` node, with its linked test(s) and their
pass/fail status (and a row, marked "—", for a CQ that has no test yet). That is
question-level coverage.

What it cannot tell you is *how much of the ontology those questions actually
exercise*. Two gaps in particular:

- **No overall percentage.** You can't see, at a glance, that (say) 6 of 7
  declared terms are used.
- **No list of untested terms.** A class or property can be declared in the
  ontology and never touched by any CQ — the current report is silent about it.

For an ontology that is *specified by* its competency questions, "which declared
terms does no CQ need?" is a first-class question. An unused term is either a
missing CQ or dead weight in the model — and today nothing surfaces it.

## What "covered" means

Coverage is **data-based**: a declared term is **covered** when a **passing**
test **populates it in its input data (ABox)** — the term appears as an instance
type (`?x a ex:C`) or an asserted predicate (`?s ex:p ?o`). Data-only counts:
even when no query names the class, a property-path query can still consume the
instance by IRI, so the instance may well be load-bearing (a stronger, per-test
check via *mutation testing* is future work).

Both dimensions are still recorded and shown per term, because a term named
**only** in a query but never instantiated — a **query-only** term (e.g. a
superclass reached through an `a/rdfs:subClassOf*` path) — is treated as a
**gap, not coverage**: the test can pass without any instance of it, so it
proves nothing about the term. Query-only is often a symptom of a TBox axiom
that has been smuggled into the fixture (see *TBox axioms in test data* below).

### TBox declarations must not count

A CQ spec frequently loads the ontology itself into its `given` (for example so
a `rdfs:subClassOf*` path can traverse the class hierarchy). The ontology
*declares* every term — but **declaring is not using**. Usage is therefore
detected from `rdf:type` **objects** and asserted **predicates**, which
structurally ignores `owl:Class` / `rdfs:subClassOf` / `rdfs:domain` axioms. So
loading the ontology as a `given` never inflates the score.

### Gate on passing tests

A term only genuinely helps answer a CQ if that CQ's test passes. When the CQ
results are available, only specs with status `passed` are credited.

## The term roles

Three source signals — data / SPARQL / structural — classify every declared term.
This is the real documentation value of the report:

| In data | In SPARQL | Structural | Role | Counts? |
|:---:|:---:|:---:|------|---------|
| ✅ | ✅ | | **fully exercised** | ✅ **covered** — populated *and* queried; strongest evidence the term works |
| ✅ | ❌ | | **data-only** | ✅ **covered** — instances exist; a property-path query may consume them by IRI without naming the class (to be confirmed by mutation testing). Candidate for a dedicated query. |
| ❌ | ✅ | | **query-only** | ❌ **not covered** — matched by a query (e.g. via `subClassOf*`) but never instantiated; the test passes without it. Usually means a TBox axiom belongs in the ontology, not the fixture. |
| ❌ | ❌ | ✅ | **structural** | 🔧 **excluded** — not instantiated/queried, but structural rather than dead weight: the domain/range of a *used* property, the superclass of a *used* class, or a metadata property (`owl:AnnotationProperty` / `owl:OntologyProperty`). Excluded from the denominator, not counted as a gap. |
| ❌ | ❌ | · | **unused** | ❌ **not covered** — declared but neither instantiated, queried, nor structurally referenced — dead weight until a test needs it |

### Why a "structural" category

A root class like `place:Place` is rarely instantiated or named in a query, yet
it is the `rdfs:domain`/`rdfs:range` of `place:isLocatedIn` and the superclass of
the classes the CQs do use. That structural role is deliberate — it supports
documentation and inferencing — so flagging it as an untested "gap" would be
misleading. Such terms are reported separately and excluded from the coverage
percentage; the headline `covered/denominator` counts only terms that *could*
be directly exercised. The denominator's total is still shown, so nothing is
hidden. A term is only classified structural when it supports a **used** term — a
superclass of only-unused classes stays a genuine gap.

Annotation and ontology properties (`owl:AnnotationProperty`,
`owl:OntologyProperty`) are documentation/metadata vocabulary rather than the
domain terms CQs are meant to exercise, so an unused one is likewise reported as
**structural** rather than flagged as a gap. If a CQ actually exercises one (in data
or SPARQL) it still counts as covered.

### "Requires ontology to pass"

The flip side of not counting the ontology as input data: when a CQ's query only
matches its `given` *through* the ontology, that dependency is itself worth
surfacing. A query that asks for a class (say `place:AdministrativeDivision`)
while the data holds instances of a **subclass** (`place:Province`) can only
match if the `rdfs:subClassOf` axioms are loaded as an input — the ontology is a
required input dataset for the test to pass. Such CQs are flagged **requires
ontology to pass** in the per-CQ section. A CQ whose query matches the data
directly (the queried types are the instantiated types) is not flagged.

### TBox axioms in test data

The same detection that keeps declarations from inflating the score also tells
us when a fixture is carrying schema it shouldn't. A `given` should hold
*instance* data; class/property declarations and `rdfs:subClassOf`/`domain`/
`range` axioms belong in the ontology. When they appear in a `given` — often so
a `subClassOf*` query path resolves — the report lists them under **⚠️ TBox
axioms in test data**, per test, with a suggestion to move them into an ontology
loaded via `:hasOntologyPath`. This is usually the root cause behind a
**query-only** term: the query only matches because the fixture supplied the
axiom the ontology should own.

## Worked example

Two ontologies — a place vocabulary and a small governance vocabulary that
reuses it (11 declared terms in total) — exercised by four mustrd tests, with
four `cq:CompetencyQuestion` nodes (three linked to a test via `cq:cqSpec`,
one with no test yet), produce the report in
[`examples/geography-example/report/term-coverage-example.md`](examples/geography-example/report/term-coverage-example.md),
generated from the runnable fixtures in
[`examples/geography-example/`](examples/geography-example/) — see the README
there for the command, and `test/test_coverage_plugin.py` which asserts it stays
correct. The headline: **8/9 terms (89%)** covered by the tests, of which
**7/9 (78%)** are backed by a competency question. Two declared terms are
reported as **structural** and excluded from the denominator: `place:Place` (the
abstract root) and `place:basedOnStandard` (an `owl:OntologyProperty`).
`gov:Mayor` is a subclass of `foaf:Person`, but `foaf:Person` is only referenced,
not declared, so it is not counted.

The all-tests gap is `place:AdministrativeDivision`: the division CQ *queries* it
but no test ever *instantiates* it (the data holds a `place:Province` and relies
on a `subClassOf` axiom smuggled into the fixture), so it is **query-only** — not
covered — and the report both flags it and lists that axiom under **⚠️ TBox
axioms in test data**. The gap between the two percentages is `place:Region`: the
non-CQ `region-lookup` test covers it in data (so it is **covered**), but no
competency question does (so its **CQ Term Coverage** column is ❌). The example also
shows two **⚠️ Used but not declared** terms — `place:hasEconomicArea` (in a
`given`, tagged *input data*) and `gov:appointedOn` (in the mayor query, tagged
*SPARQL*) — each likely a typo or missing definition, listed with the test that
references it.

The value the CQ table cannot give today: a percentage, the structural
terms called out separately, and — when one exists — the exact list of declared
terms no CQ touches at all.

## How it's implemented

Reuses what mustrd already parses — no new config:

1. The flags opt in (checked in `pytest_configure`). In `pytest_sessionfinish`,
   for each collected `TestSpec` we read the merged `given` graph, the `when`
   query text(s), the pass/fail result, and the spec's IRI. Separately, every
   `cq:CompetencyQuestion` node in the suite's `*.mustrd.ttl` files is collected
   and its `cq:cqSpec` links resolved against those specs (a CQ may point at
   0..n specs, or none).
2. Coverage is **data-based**: a declared term is covered when a *passing* test
   populates it in its input data (an `rdf:type` object or asserted predicate). A
   term only named in a query but never instantiated is *query-only* — a gap, not
   coverage. The CQ overlay measures the same way over the specs the CQs link to.
3. **Declared terms** come from the ontology named by `mustrdTest:hasOntologyPath`
   (files and/or recursively-scanned directories, merged into one graph):
   subjects typed `owl:Class` / `rdf:Property` / …, restricted to non-well-known
   namespaces (so `rdfs:label` etc. aren't mistaken for the ontology under test).
   `--term-coverage` with no `hasOntologyPath` fails early.
4. **Structural references** are found over the union of the given graphs: the
   `rdfs:domain`/`rdfs:range` of each used property and the superclasses of each
   used class. Declared terms that are only structurally referenced are excluded
   from the denominator.
5. The report is assembled from per-section templates — `md_ontologies_template`,
   `md_term_coverage_template`, `md_tbox_in_data_template`, `md_cq_table_template`,
   `md_duplicate_cqs_template`, `md_cq_gaps_template`, `md_per_cq_template` —
   printed to stdout via the terminal reporter and written to the `--md` file
   (whose parent directory is created if missing).

The code is split into three layers, one-directional (`ontology.py` <-
`coverage.py` <- `cq.py`):

- **`mustrd/ontology.py`** — the pure RDF read layer: `load_ontology` /
  `ontology_report` / `expand_ontology_files`, `declared_terms` /
  `metadata_terms`, `abox_terms` / `query_uris`, and the namespace / prefix
  helpers. Knows nothing about specs or coverage.
- **`mustrd/coverage.py`** — term-coverage scoring: the structural (schema)
  reasoning, the subClassOf term tree, "used but not declared", "TBox axioms in
  test data", and `compute_coverage`.
- **`mustrd/cq.py`** — the competency-question overlay: duplicate-question
  detection, `cq:cqSpec` resolution, the per-CQ breakdown, and `cq_only_view`
  (`--cq` with no ontology).
- **`mustrd/coverage_rdf.py`** — serialises a run to the canonical RDF graph
  (both halves): coverage measurements/terms/issues, and CQ nodes with a
  `cov:Assertion` per linked test. `cq_graph` builds a CQ-only graph for `--cq`
  with no ontology.
- **`mustrd/coverage_render.py`** / **`mustrd/cq_render.py`** — rebuild the
  Coverage Report and Competency Questions Report template contexts **from that
  graph** (+ the ontology, for the tree). The **whole report** is therefore a pure
  function of the RDF, tested at two levels: `compute → graph` (data) and
  `graph → Markdown` (rendering).

Also: `mustrd/TestResult.py` render helpers; the `--term-coverage` / `--cq`
options, CQ-node collection, `:hasOntologyPath` parsing and the fail-early check
in `mustrd/mustrdTestPlugin.py`; the competency-question vocabulary
(`cq:CompetencyQuestion`, `cq:question`, `cq:cqSpec`; namespace
`https://mustrd.org/competencyQuestion/`, prefix `cq:`) in its own
`mustrd/model/cq-ontology.ttl` with the matching `cq:CompetencyQuestionShape` in
`mustrd/model/mustrdShapes.ttl`; the `CQ` namespace in `mustrd/namespace.py`; the
`:hasOntologyPath` term in `mustrd/model/mustrdTestOntology.ttl`. Tests in
`test/test_coverage.py` (unit) and `test/test_coverage_plugin.py` (end-to-end).

### Report links

The report links each referenced file (ontologies, spec `.mustrd.ttl`s). Where
those links point depends on where the report is read:

- **Locally / committed in the repo** — links are **relative** to the report
  file. A Markdown previewer (VS Code) and GitHub's own file view both resolve
  them against the report's location.
- **In a GitHub Actions job summary** — the summary is rendered on the
  `…/actions/runs/…` page, so relative links don't resolve. When mustrd detects
  it is running as an Action (`GITHUB_ACTIONS=true`) it emits **absolute** URLs
  into the repo web UI — `{GITHUB_SERVER_URL}/{GITHUB_REPOSITORY}/blob/{GITHUB_SHA}/{path}`
  (path relative to `GITHUB_WORKSPACE`). No configuration is needed; those
  variables are injected by the Actions runner.

### RDF output (`--term-coverage-rdf`)

Coverage is a **quality of the ontology** (as exercised by the tests), so it is
published as RDF and merged into a knowledge graph. This graph is the
**canonical output** of a coverage run — the Coverage Report Markdown is rendered
*from it* (see the module list above), not the other way round.
`--term-coverage-rdf=PATH` writes a Turtle graph using **W3C DQV** (Data Quality
Vocabulary) + **PROV-O**, plus a small `cov:` vocabulary in
[`mustrd/model/coverage-ontology.ttl`](../mustrd/model/coverage-ontology.ttl)
(namespace `https://mustrd.org/coverage/`):

- **Aggregate** — a `dqv:QualityMeasurement` for `cov:termCoverageByTests` (and,
  with `--cq`, `cov:termCoverageByCompetencyQuestions`), value a decimal **ratio**
  (0–1; the % is display-only), `dqv:computedOn` **each ontology IRI and its
  `owl:versionIRI`**, `prov:wasGeneratedBy` the run.
- **Per term** — a `cov:TermCoverage` for every declared term: `cov:term` the
  actual term IRI, `cov:kind`, `cov:role` / `cov:cqRole` a `cov:CoverageRole`
  (Covered / QueryOnly / Structural / Unused), `cov:inData` / `cov:inQuery`, a
  `cov:structuralReason` when structural, and a `cov:exercise` per backing test
  (`cov:Exercise` → `cov:test` + its own `cov:inData` / `cov:inQuery`). Every
  triple is kept, so the whole report is reconstructable and the aggregate is
  explainable from the graph.
- **Quality issues** — `cov:QualityIssue` for *used but not declared* and *TBox in
  test data*, linked to the term / test.
- **Competency questions** — each `cq:CompetencyQuestion` node (its `cq:question`
  and `cq:cqSpec` links) with a `cov:Assertion` per linked test (`cov:onTest`,
  `cov:outcome` Passed/Failed, and `cov:requiresOntology` → the **ontology IRI**
  the test only matches its data *through*, when applicable). A duplicate-question
  CQ gets a `cov:Assertion` too — `cov:onCompetencyQuestion` it, `cov:duplicateOf`
  its peer(s) — so the duplication is a run *finding*, not a triple on the CQ node.
  These are object references, not booleans: presence carries the context (which
  ontology, which peer CQs), and the renderer derives the yes/no flags it shows.
  Each test also records its `cov:usesInData`/`usesInQuery` domain terms. This is
  what CQ↔test/term linking looks like in the graph, and what the Competency
  Questions Report is rendered from.
- **Provenance** — a `cov:CoverageRun` (`prov:Activity`) with the mustrd agent,
  `prov:used` the ontologies, `prov:startedAtTime` when it ran, `cov:gitCommit`
  the revision (and `cov:commit` / `cov:ciRun` links to the commit page and CI job
  when hosted). Each run gets a **fresh** minted IRI (a UUID, or `MUSTRD_RUN_ID`
  if set) so successive runs **accumulate** in a knowledge graph rather than
  clobber; every child IRI is minted under it, and there are no blank nodes, so
  runs still merge and diff cleanly.

Because the tests, competency questions and ontology terms are all real IRIs, a
consumer can query across the merged graph — e.g. coverage % per ontology version
over time, which terms carry a quality issue, or which competency question pins
down a given term. See
[`report/term-coverage-example.ttl`](examples/geography-example/report/term-coverage-example.ttl).

### Known limitations / open questions

- **Namespace filtering** — declared terms are read from the configured
  ontology and filtered against a fixed well-known-vocabulary list
  (`rdf`, `rdfs`, `owl`, `xsd`, `skos`, `sh`, `mustrd`, `dc`, `dcterms`, `prov`).
  Terms in other imported vocabularies loaded via `hasOntologyPath` would be
  counted; scoping to a specific namespace is not yet configurable.
- **Schema heuristic** — a term is treated as structural when it is the
  domain/range of a used property or a superclass of a used class. Other
  structural roles (e.g. `owl:Restriction` fillers, property chains) are not yet
  recognised and would still show as gaps.
- **Multiple ontologies / imports** — all non-well-known declared terms are
  pooled; scoping per-vocabulary is not yet supported.

## Why this belongs in mustrd

mustrd already knows each spec's given, query, and pass/fail status. It is the
natural place to close the loop from "my CQs pass" to "my CQs exercise my
ontology" — turning a suite of Given-When-Then specs into a coverage signal for
the model they validate.
