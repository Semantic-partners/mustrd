# Ontology term-coverage example

A small, runnable mustrd suite that demonstrates the `--term-coverage` and `--cq`
features (see [`../../ontology-term-coverage.md`](../../ontology-term-coverage.md)
for the design). **Two** ontologies — a place vocabulary and a small governance
vocabulary that reuses it — are exercised by four mustrd tests (three with a
competency question, one without). The report shows which declared terms the
tests exercise across both ontologies, and how much of that is backed by a
competency question.

## Layout

| Path | What it is |
|------|------------|
| [`mustrd-config.ttl`](mustrd-config.ttl) | The suite config — points at the specs, data, and the ontologies. `:hasOntologyPath` is repeated, once per ontology. |
| [`ontology/place.ttl`](ontology/place.ttl) | Places (`Place`, `City`, `Country`, …) and `isLocatedIn`, plus an ontology-level metadata property. |
| [`ontology/governance.ttl`](ontology/governance.ttl) | A second ontology: `Mayor` (a subclass of `foaf:Person`) and `governs`, which ranges over `place:City` — so it reuses both an external vocabulary and the place one. |
| [`data/`](data/) | The `given` instance data for each spec. |
| [`specs/`](specs/) | The three competency-question specs (`must:competencyQuestion`, a `SELECT` `when`, and a `then` table), plus one **non-CQ** spec (`region-lookup.mustrd.ttl`). The mayor spec binds the city with `must:hasBinding` (`?city` → `ex:Rotterdam`) rather than hard-coding it, and its data includes a second city's mayor as a distractor to prove the query really discriminates. |
| [`report/term-coverage-example.md`](report/term-coverage-example.md) | The generated report (committed so it can be viewed on GitHub). |

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
their combined declared terms (11 declared, 2 excluded as **schema**):

- `place:Place` — the abstract root; not instantiated or queried, but the
  `rdfs:domain`/`rdfs:range` of `place:isLocatedIn` and the superclass of the
  classes the tests use.
- `place:basedOnStandard` — an `owl:OntologyProperty`; ontology-level metadata.

**Two coverage numbers:** the tests exercise **9/9 = 100%** of the (non-schema)
terms, but only **8/9 = 89%** are backed by a **competency question**. The one
difference is `place:Region`: `region-lookup.mustrd.ttl` exercises it (in data
and SPARQL) and passes, but it has no `must:competencyQuestion` — so `place:Region`
is *covered* yet its **By a CQ?** column is ❌. That's the whole point of the two
metrics: all-test coverage says nothing's dead; CQ coverage says which
*requirements* actually pin the term down.

**Failure signals:** `place:hasEconomicArea` (in the country spec's data) and
`gov:appointedOn` (in the mayor spec's SPARQL) are used but never declared in
their ontologies, so they appear under **⚠️ Used but not declared** — likely
typos or missing definitions. Each lists the referencing test and whether it was
seen in the input data or the SPARQL.

**External vocabularies aren't counted:** `gov:Mayor` is a subclass of
`foaf:Person` and `gov:governs`'s domain is `foaf:Person`, but `foaf:Person`
is only *referenced*, not *declared* here — so it never appears in coverage. Only
terms the ontologies under test actually declare are measured. (Contrast with
`place:hasEconomicArea`, which *is* in an ontology's namespace, so its absence is
flagged.)

It also shows the **requires ontology to pass** flag: the division CQ queries
`place:AdministrativeDivision` but its data holds a `place:Province`, so it only
matches through the `rdfs:subClassOf` axioms — the ontology must be loaded as an
input for that test to pass. The country CQ queries types that are instantiated
directly, so it is not flagged.

> The ontology uses a `place:` prefix rather than `geo:` — rdflib pre-binds
> `geo:` to GeoSPARQL, which would rename an author's `geo:` to `geo1:` in the
> report output.
