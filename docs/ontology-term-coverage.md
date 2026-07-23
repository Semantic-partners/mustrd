# Ontology term coverage

**Status:** Implemented (draft PR).

Two independent, opt-in flags:

- **`--term-coverage`** — ontology term coverage over **all mustrd tests**. It
  needs an ontology (`:hasOntologyPath`) and produces:
  1. **Ontologies** — the files measured against, as clickable links (relative to
     the report so they render in a Markdown previewer), each with the
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

The flags **compose**. With both, coverage gains a CQ overlay: a second headline
percentage (how much of the ontology the *competency questions* cover, vs all
tests), a **By a CQ?** column per term, a second **Not used by any CQ** gap list
(CQ-scoped, alongside the all-tests one), a Coverage Status column in the CQ
table, and — because duplicate `must:competencyQuestion` values are usually a
copy/paste slip — those CQs are excluded from the CQ overlay and listed under a
*Duplicate competency questions* warning.

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

The CQ table added in `feature/cq_parsing` answers *"which competency questions
have a passing test?"* — one row per spec, with a pass/fail status. That is
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

## What "used" means

To *answer* a competency question you need both the input data and the query,
and ontology terms are split across the two. So this proposal defines a declared
term as **used** if a **passing** CQ test exercises it in **either** place:

- **in the input data (ABox):** the term appears as an instance type
  (`?x a ex:C`) or as an asserted predicate (`?s ex:p ?o`); **or**
- **in the SPARQL query:** the term's IRI appears in the parsed query algebra.

This split is deliberate — it captures both:

- **query-only** terms: named by the query but never instantiated (e.g. a
  superclass reached through an `a/rdfs:subClassOf*` path); and
- **data-only** terms: populated in the fixture but never named by any query.

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

| In data | In SPARQL | Structural | Role | Meaning |
|:---:|:---:|:---:|------|---------|
| ✅ | ✅ | | **fully exercised** | populated *and* queried — strongest evidence the term works |
| ✅ | ❌ | | **data-only** | instances exist but no CQ asks about it — candidate for a new CQ |
| ❌ | ✅ | | **query-only** | matched by a query (e.g. via `subClassOf*`) but never instantiated — relies on inference, not asserted data |
| ❌ | ❌ | ✅ | **structural** | not instantiated/queried, but structural rather than dead weight — the domain/range of a *used* property, the superclass of a *used* class, or a metadata property (`owl:AnnotationProperty` / `owl:OntologyProperty`) — so **excluded from the coverage denominator** rather than counted as a gap |
| ❌ | ❌ | · | **unused** | declared but neither instantiated, queried, nor structurally referenced — dead weight until a CQ needs it |

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

## Worked example

Two ontologies — a place vocabulary and a small governance vocabulary that
reuses it (11 declared terms in total) — exercised by four mustrd tests (three
with a competency question, one without) produce the report in
[`examples/geography-example/report/term-coverage-example.md`](examples/geography-example/report/term-coverage-example.md),
generated from the runnable fixtures in
[`examples/geography-example/`](examples/geography-example/) — see the README
there for the command, and `test/test_coverage_plugin.py` which asserts it stays
correct. The headline: **9/9 terms (100%)** exercised by the tests, of which
**8/9 (89%)** are backed by a competency question. Two declared terms are
reported as **structural** and excluded from the denominator: `place:Place` (the
abstract root) and `place:basedOnStandard` (an `owl:OntologyProperty`).
`gov:Mayor` is a subclass of `foaf:Person`, but `foaf:Person` is only referenced,
not declared, so it is not counted.

The single-term gap between the two percentages is `place:Region`: the non-CQ
`region-lookup` test exercises it (so it is **covered**), but no competency
question does (so its **By a CQ?** column is ❌). The example also shows two
**⚠️ Used but not declared** terms — `place:hasEconomicArea` (in a `given`,
tagged *input data*) and `gov:appointedOn` (in the mayor query, tagged *SPARQL*)
— each likely a typo or missing definition, listed with the test that references
it.

The value the CQ table cannot give today: a percentage, the structural
terms called out separately, and — when one exists — the exact list of declared
terms no CQ touches at all.

## How it's implemented

Reuses what mustrd already parses — no new config:

1. `--term-coverage` opts in (checked in `pytest_configure`). In
   `pytest_sessionfinish`, for each collected `TestSpec` we read the merged
   `given` graph, the `when` query text(s), and the pass/fail result mustrd
   already has.
2. `mustrd/coverage.py` computes ABox usage (`rdf:type` objects + asserted
   predicates in the given) ∪ query usage (IRIs from the parsed SPARQL algebra),
   crediting only specs whose result is `passed`.
3. **Declared terms** come from the ontology named by `mustrdTest:hasOntologyPath`
   (files and/or recursively-scanned directories, merged into one graph):
   subjects typed `owl:Class` / `rdf:Property` / …, restricted to non-well-known
   namespaces (so `rdfs:label` etc. aren't mistaken for the ontology under test).
   `--term-coverage` with no `hasOntologyPath` fails early.
4. **Schema references** are found over the union of the given graphs: the
   `rdfs:domain`/`rdfs:range` of each used property and the superclasses of each
   used class. Declared terms that are only structurally referenced are excluded from
   the denominator.
5. The report is assembled from three templates — `md_ontologies_template.jinja`
   (files + `owl:Ontology` IRI + description, via `coverage.ontology_report`),
   `md_cq_table_template.jinja`, and `md_term_coverage_template.jinja` — printed
   to stdout via the terminal reporter and written to the `--md` file (whose
   parent directory is created if missing).

Files: `mustrd/coverage.py` (incl. `ontology_report`), the
`md_ontologies_template.jinja` / `md_cq_table_template.jinja` (now headed
"Competency Questions") / `md_term_coverage_template.jinja` templates,
`mustrd/TestResult.py` (`render_ontologies` / `render_term_coverage`), the
`--term-coverage` option,
`:hasOntologyPath` config parsing and the fail-early check in
`mustrd/mustrdTestPlugin.py`, the `:hasOntologyPath` term in
`mustrd/namespace.py` + `mustrd/model/mustrdTest{Ontology,Shapes}.ttl`. Unit
tests in `test/test_coverage.py`.

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
