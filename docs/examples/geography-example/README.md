# Ontology term-coverage example

A small, runnable mustrd suite that demonstrates the `--term-coverage` feature
(see [`../../ontology-term-coverage.md`](../../ontology-term-coverage.md) for the
design). **Two** ontologies — a place vocabulary and a small governance
vocabulary that reuses it — are validated by three competency-question specs;
the report shows which declared terms those passing CQs actually exercise, across
both ontologies.

## Layout

| Path | What it is |
|------|------------|
| [`mustrd-config.ttl`](mustrd-config.ttl) | The suite config — points at the specs, data, and the ontologies. `:hasOntologyPath` is repeated, once per ontology. |
| [`ontology/place.ttl`](ontology/place.ttl) | Places (`Place`, `City`, `Country`, …) and `isLocatedIn`, plus an ontology-level metadata property. |
| [`ontology/governance.ttl`](ontology/governance.ttl) | A second ontology: `Mayor` (a subclass of `foaf:Person`) and `governs`, which ranges over `place:City` — so it reuses both an external vocabulary and the place one. |
| [`data/`](data/) | The `given` instance data for each spec. |
| [`specs/`](specs/) | The three competency-question specs (`must:competencyQuestion`, a `SELECT` `when`, and a `then` table). The mayor spec binds the city with `must:hasBinding` (`?city` → `ex:Rotterdam`) rather than hard-coding it, and its data includes a second city's mayor as a distractor to prove the query really discriminates. |
| [`report/term-coverage-example.md`](report/term-coverage-example.md) | The generated report (committed so it can be viewed on GitHub). |

## Run it

From the repo root, scoped to this directory so only these specs run:

```bash
(cd docs/examples/geography-example && \
   pytest . --mustrd --config=mustrd-config.ttl --term-coverage \
          --md=report/term-coverage-example.md)
```

This regenerates [`report/term-coverage-example.md`](report/term-coverage-example.md).
Links in the report are relative to that file, so they resolve in a Markdown
previewer. CI runs the same command, and `test/test_coverage_plugin.py` asserts
the report stays correct.

## What it shows

**Multiple ontologies:** the report's *Ontologies* section lists both files
(each with its `owl:Ontology` IRI and description), and coverage is measured
against their combined declared terms — **8/9 domain terms covered (89%)** across
11 declared. Two are reported as **schema** terms (excluded from the denominator
rather than counted as gaps):

- `place:Place` — the abstract root; not instantiated or queried, but the
  `rdfs:domain`/`rdfs:range` of `place:isLocatedIn` and the superclass of the
  classes the CQs use.
- `place:basedOnStandard` — an `owl:OntologyProperty`; ontology-level metadata,
  not part of the domain vocabulary the CQs exercise.

**Failure signals:** the example deliberately shows two problems the report
catches:

- `place:Region` is declared but no CQ exercises it — a genuine **gap** (the
  1-of-9 that drops coverage below 100%), listed under *Not used by any CQ*.
- `place:hasEconomicArea` is used in the country spec's data but never declared
  in `place.ttl`, so it appears under **⚠️ Used but not declared** — a likely typo
  or missing definition.

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
