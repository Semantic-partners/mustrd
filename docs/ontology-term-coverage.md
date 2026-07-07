# Proposal: Ontology term coverage from competency-question specs

**Status:** Draft / RFC — proposal only, no implementation in this PR.
**Builds on:** `feature/cq_parsing` (the `must:CompetencyQuestion` annotation and
the CQ results table).

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

## The four term roles

The two source columns (data / SPARQL) classify every declared term into one of
four roles — this is the real documentation value of the report:

| In data | In SPARQL | Role | Meaning |
|:---:|:---:|------|---------|
| ✅ | ✅ | **fully exercised** | populated *and* queried — strongest evidence the term works |
| ✅ | ❌ | **data-only** | instances exist but no CQ asks about it — candidate for a new CQ |
| ❌ | ✅ | **query-only** | matched by a query (e.g. via `subClassOf*`) but never instantiated — relies on inference, not asserted data |
| ❌ | ❌ | **unused** | declared but neither instantiated nor queried — dead weight until a CQ needs it |

## Worked example

A small geography ontology (7 declared terms) with two competency questions —
*"In which country is Rotterdam?"* and *"In what administrative division of what
country is Rotterdam?"* — produces the report in
[`examples/term-coverage-example.md`](examples/term-coverage-example.md):
**6/7 terms (86%)**, with `geo:Place` (an abstract root class) flagged as the
one term no CQ exercises.

That single line — *`geo:Place`: declared, never used* — is exactly the signal
the CQ table cannot give today.

## Proposed integration (sketch, not in this PR)

Reuse what mustrd already parses:

1. For each `TestSpec`: read the `must:given` datasets and the `must:when`
   query — mustrd resolves both already.
2. Compute ABox usage (`rdf:type` objects + asserted predicates in the merged
   given) ∪ query usage (IRIs from the parsed SPARQL algebra).
3. Join against the ontology's declared terms (subjects typed `owl:Class` /
   `rdf:Property` / …), restricted to the ontology's own namespace(s).
4. Credit only specs whose result status is `passed`.
5. Emit a Markdown section alongside the existing CQ table — overall %, the
   per-term table above, an explicit unused-terms list, and a per-CQ breakdown.

Open questions for discussion:

- **Namespace selection** — infer the ontology namespace(s) from
  `owl:Ontology` / declared-term prefixes, or take an explicit config value?
- **Abstract classes** — should intentionally-abstract superclasses be
  excludable from the denominator, or always counted (and merely flagged)?
- **Report surface** — extend the existing `--md` table, or a separate
  `--term-coverage` output?
- **Multiple ontologies / imports** — how to scope "declared terms" when specs
  span several vocabularies.

## Why this belongs in mustrd

mustrd already knows each spec's given, query, and pass/fail status. It is the
natural place to close the loop from "my CQs pass" to "my CQs exercise my
ontology" — turning a suite of Given-When-Then specs into a coverage signal for
the model they validate.
