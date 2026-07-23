# Ontology term-coverage example

A small, runnable mustrd suite that demonstrates the `--term-coverage` and `--cq`
features (see [`../../ontology-term-coverage.md`](../../ontology-term-coverage.md)
for the design). **Two** ontologies — a place vocabulary and a small governance
vocabulary that reuses it — are exercised by four mustrd tests. Four
`must:CompetencyQuestion` nodes accompany them: three link to a test via
`must:cqSpec`, and one records a question with **no test yet**. The report shows
which declared terms the tests exercise across both ontologies, and how much of
that is backed by a competency question.

## Layout

| Path | What it is |
|------|------------|
| [`mustrd-config.ttl`](mustrd-config.ttl) | The suite config — points at the specs, data, and the ontologies. `:hasOntologyPath` is repeated, once per ontology. |
| [`ontology/place.ttl`](ontology/place.ttl) | Places (`Place`, `City`, `Country`, …) and `isLocatedIn`, plus an ontology-level metadata property. |
| [`ontology/governance.ttl`](ontology/governance.ttl) | A second ontology: `Mayor` (a subclass of `foaf:Person`) and `governs`, which ranges over `place:City` — so it reuses both an external vocabulary and the place one. |
| [`data/`](data/) | The `given` instance data for each spec. |
| [`specs/`](specs/) | Three test specs, each paired in-file with a `must:CompetencyQuestion` node (`must:question` + `must:cqSpec`), a `SELECT` `when`, and a `then` table; one **non-CQ** spec (`region-lookup.mustrd.ttl`); and [`population-of-rotterdam.mustrd.ttl`](specs/population-of-rotterdam.mustrd.ttl), a CQ node with **no test** at all. The mayor spec binds the city with `must:hasBinding` (`?city` → `ex:Rotterdam`) rather than hard-coding it, and its data includes a second city's mayor as a distractor to prove the query really discriminates. |
| [`report/term-coverage-example.md`](report/term-coverage-example.md) | The generated report (committed so it can be viewed on GitHub). |
| [`ontologies.html`](ontologies.html) | A standalone visual of the two ontologies — class hierarchy and properties, colour-coded by namespace. Open it in a browser. |

## Run it

From the repo root, scoped to this directory so only these specs run:

```bash
(cd docs/examples/geography-example && \
   pytest . --mustrd --config=mustrd-config.ttl --term-coverage --cq \
          --md=report/term-coverage-example.md)
```

This regenerates [`report/term-coverage-example.md`](report/term-coverage-example.md).
Links in the report are relative to that file, so they resolve in a Markdown
previewer. CI runs the same command, and `test/test_coverage_plugin.py` asserts
the report stays correct.

## What it shows

**Multiple ontologies:** the report's *Ontologies* section lists both files
(each with its `owl:Ontology` IRI and description); coverage is measured against
their combined declared terms (11 declared, 2 excluded as **structural**):

- `place:Place` — the abstract root; not instantiated or queried, but the
  `rdfs:domain`/`rdfs:range` of `place:isLocatedIn` and the superclass of the
  classes the tests use.
- `place:basedOnStandard` — an `owl:OntologyProperty`; ontology-level metadata.

**Two coverage numbers:** coverage is *data-based* (a term must be populated in
some passing test's input data to count). The tests cover **8/9 = 89%** of the
(non-structural) terms, and **7/9 = 78%** are backed by a **competency
question**. Two things drive those numbers:

- `place:AdministrativeDivision` is **query-only** — the division CQ *queries* it
  but no test *instantiates* it (see *query-only* below), so it is **not
  covered** and drops the all-tests number to 89%.
- `place:Region` is *covered* but not by a CQ: `region-lookup.mustrd.ttl` covers
  it (in data and SPARQL) and passes, but no `must:CompetencyQuestion` links to it
  — so its **CQ Term Coverage** column is ❌, taking the CQ number down to 78%.

That's the point of the two metrics: all-test coverage says what's exercised at
all; CQ coverage says which *requirements* actually pin a term down.

**Query-only is a gap, not coverage:** `place:AdministrativeDivision` shows how a
term can be *named* by a query yet prove nothing. The division CQ asks for
`place:AdministrativeDivision`, but its `given` holds a `place:Province` and a
`place:Province rdfs:subClassOf place:AdministrativeDivision` axiom — so the query
only matches *through* that axiom. The report marks the term **❌ query only**,
lists it under **Not covered by any test**, and — because that `subClassOf` axiom
is TBox living in a fixture — surfaces it under **⚠️ TBox axioms in test data**
with a suggestion to move it into the ontology.

**Failure signals:** `place:hasEconomicArea` (in the country spec's data) and
`gov:appointedOn` (in the mayor spec's SPARQL) are used but never declared in
their ontologies, so they appear under **⚠️ Used but not declared** — likely
typos or missing definitions. Each lists the referencing test and whether it was
seen in the input data or the SPARQL.

**External vocabularies aren't counted:** `gov:Mayor` is a subclass of
`foaf:Person` and `gov:governs`'s domain is `foaf:Person`. `foaf:Person` is only
*referenced*, not *declared* here, so it shows in the term tree as an *external*
**structural** row (the head of the `gov:Mayor` / `gov:governs` branch) but is
**excluded from the percentage** — only terms the ontologies under test declare
count. (Contrast with `place:hasEconomicArea`, which *is* in an ontology's
namespace, so its absence is flagged as *used but not declared*.)

It also shows the **requires ontology to pass** flag: the division CQ queries
`place:AdministrativeDivision` but its data holds a `place:Province`, so it only
matches through the `rdfs:subClassOf` axioms — the ontology must be loaded as an
input for that test to pass. The country CQ queries types that are instantiated
directly, so it is not flagged.

> The ontology uses a `place:` prefix rather than `geo:` — rdflib pre-binds
> `geo:` to GeoSPARQL, which would rename an author's `geo:` to `geo1:` in the
> report output.
