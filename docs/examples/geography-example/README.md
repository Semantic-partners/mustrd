# Ontology term-coverage example

A small, runnable mustrd suite that demonstrates the `--term-coverage` feature
(see [`../../ontology-term-coverage.md`](../../ontology-term-coverage.md) for the
design). A tiny geography ontology is validated by two competency-question specs;
the report shows which declared terms those passing CQs actually exercise.

## Layout

| Path | What it is |
|------|------------|
| [`mustrd-config.ttl`](mustrd-config.ttl) | The suite config — points at the specs, data, and ontology (`:hasOntologyPath`). |
| [`ontology/geography.ttl`](ontology/geography.ttl) | The ontology under test: places (`Place`, `City`, `Country`, …) and `isLocatedIn`, plus an ontology-level metadata property. |
| [`data/`](data/) | The `given` instance data for each spec. |
| [`specs/`](specs/) | The two competency-question specs (`must:competencyQuestion`, a `SELECT` `when`, and a `then` table). |
| [`report/term-coverage-example.md`](report/term-coverage-example.md) | The generated report (committed so it can be viewed on GitHub). |

## Run it

From the repo root, scoped to this directory so only these two specs run:

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

**6/6 domain terms covered (100%)** across 8 declared terms. The two excluded
from the denominator are reported as **schema** terms rather than gaps:

- `place:Place` — the abstract root; not instantiated or queried, but the
  `rdfs:domain`/`rdfs:range` of `place:isLocatedIn` and the superclass of the
  classes the CQs use.
- `place:basedOnStandard` — an `owl:OntologyProperty`; ontology-level metadata,
  not part of the domain vocabulary the CQs exercise.

It also shows the **requires ontology to pass** flag: the division CQ queries
`place:AdministrativeDivision` but its data holds a `place:Province`, so it only
matches through the `rdfs:subClassOf` axioms — the ontology must be loaded as an
input for that test to pass. The country CQ queries types that are instantiated
directly, so it is not flagged.

> The ontology uses a `place:` prefix rather than `geo:` — rdflib pre-binds
> `geo:` to GeoSPARQL, which would rename an author's `geo:` to `geo1:` in the
> report output.
