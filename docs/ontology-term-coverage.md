# Ontology term coverage from competency-question specs

**Status:** Implemented (draft PR).
**Builds on:** `feature/cq_parsing` (the `must:CompetencyQuestion` annotation and
the CQ results table).

Ontology term coverage is **opt-in** via `--term-coverage`. When enabled, mustrd
prints an overall percentage, a per-term matrix, and the list of declared terms
no CQ exercises to **stdout**; adding `--md` also writes it to the report file
(beneath the CQ table). It is emitted only when the specs declare ontology terms
in their `given` data — ordinary suites are unaffected.

```bash
# coverage to stdout
pytest --mustrd --config=path/to/mustrd-config.ttl --term-coverage

# coverage to stdout AND appended to the md report
pytest --mustrd --config=path/to/mustrd-config.ttl --term-coverage --md=report.md
```

Without `--term-coverage`, no coverage is computed; `--md` on its own writes
just the CQ table, exactly as before.

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

Three source signals — data / SPARQL / schema — classify every declared term.
This is the real documentation value of the report:

| In data | In SPARQL | In schema | Role | Meaning |
|:---:|:---:|:---:|------|---------|
| ✅ | ✅ | | **fully exercised** | populated *and* queried — strongest evidence the term works |
| ✅ | ❌ | | **data-only** | instances exist but no CQ asks about it — candidate for a new CQ |
| ❌ | ✅ | | **query-only** | matched by a query (e.g. via `subClassOf*`) but never instantiated — relies on inference, not asserted data |
| ❌ | ❌ | ✅ | **schema** | not instantiated/queried, but domain/range of a *used* property or superclass of a *used* class — valuable for documentation and inferencing, so **excluded from the coverage denominator** rather than counted as a gap |
| ❌ | ❌ | · | **unused** | declared but neither instantiated, queried, nor structurally referenced — dead weight until a CQ needs it |

### Why a "schema" category

A root class like `geo:Place` is rarely instantiated or named in a query, yet it
is the `rdfs:domain`/`rdfs:range` of `geo:isLocatedIn` and the superclass of the
classes the CQs do use. That structural role is deliberate — it supports
documentation and inferencing — so flagging it as an untested "gap" would be
misleading. Such terms are reported separately and excluded from the coverage
percentage; the headline `covered/denominator` counts only terms that *could*
be directly exercised. The denominator's total is still shown, so nothing is
hidden. A term is only schema-classified when it supports a **used** term — a
superclass of only-unused classes stays a genuine gap.

## Worked example

A small geography ontology (7 declared terms) with two competency questions —
*"In which country is Rotterdam?"* and *"In what administrative division of what
country is Rotterdam?"* — produces the report in
[`examples/term-coverage-example.md`](examples/term-coverage-example.md):
**6/6 terms (100%)**. `geo:Place` (the abstract root) is not directly exercised
but is the domain/range of `geo:isLocatedIn` and the superclass of the used
classes, so it is reported as a **schema** term and excluded from the
denominator rather than counted as a gap.

The value the CQ table cannot give today: a percentage, the schema/structural
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
3. **Declared terms** are derived from the same given graphs — subjects typed
   `owl:Class` / `rdf:Property` / … — restricted to non-well-known namespaces
   (so `rdfs:label` etc. aren't mistaken for the ontology under test). This
   works because a CQ that needs class-hierarchy reasoning already loads the
   ontology into its `given`.
4. **Schema references** are found over the union of the given graphs: the
   `rdfs:domain`/`rdfs:range` of each used property and the superclasses of each
   used class. Declared terms that are only schema-referenced are excluded from
   the denominator.
5. The result is rendered by `templates/md_term_coverage_template.jinja` and
   appended to the `--md` report after the CQ table.

Files: `mustrd/coverage.py`, `mustrd/templates/md_term_coverage_template.jinja`,
`mustrd/TestResult.py` (`render_term_coverage`), wired in
`mustrd/mustrdTestPlugin.py`. Unit tests in `test/test_coverage.py`.

### Known limitations / open questions

- **Namespace selection** — declared terms are auto-detected from the given
  graphs and filtered against a fixed well-known-vocabulary list. An explicit
  config option (point at the ontology file, or name the namespace) would be
  more robust when the ontology is *not* loaded into any `given`.
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
