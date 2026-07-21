<!--
  Real `--md` output of the ontology-term-coverage feature, generated from the
  runnable fixtures in ./geography-example (config, ontology, data, and two CQ
  specs). To regenerate, from the repo root:

    (cd docs/examples/geography-example && \
       pytest . --mustrd --config=mustrd-config.ttl --term-coverage \
              --md=../term-coverage-example.md)

  Links are relative to this file so they render in a Markdown previewer.
  test/test_coverage_plugin.py asserts this report stays correct.
-->
# Ontologies Report

## Ontologies

Coverage below is measured against this ontology:

- [ontology/geography.ttl](geography-example/ontology/geography.ttl) — `http://geo.org/` — A minimal vocabulary for places and how they are geographically contained within one another.


## Competency Questions

| Module | Class | Test | Competency Question | Status |
|--------|-------|------|---------------------|--------|
| docs/examples/geography-example/mustrd-config.ttl | rdflib | [country-of-rotterdam.mustrd.ttl](geography-example/specs/country-of-rotterdam.mustrd.ttl) | In which country is Rotterdam? | passed |
| docs/examples/geography-example/mustrd-config.ttl | rdflib | [division-and-country-of-rotterdam.mustrd.ttl](geography-example/specs/division-and-country-of-rotterdam.mustrd.ttl) | In what administrative division of what country is Rotterdam? | passed |


## Ontology term coverage

**Overall: 6/6 terms used to answer the CQs = 100%**

_(7 declared; 1 structural/schema term(s) excluded from the denominator — see below.)_

A term is *used* if a passing CQ test exercises it — either in the **input data** (as an instance type or asserted predicate) or in the **SPARQL** query. Ontology declarations alone do not count.

| Term | Kind | In input data | In SPARQL | In schema | Status |
|------|------|:---:|:---:|:---:|:---:|
| geo:AdministrativeDivision | class | ❌ | ✅ | · | ✅ covered |
| geo:City | class | ✅ | ❌ | · | ✅ covered |
| geo:Continent | class | ✅ | ❌ | · | ✅ covered |
| geo:Country | class | ✅ | ✅ | · | ✅ covered |
| geo:Place | class | ❌ | ❌ | ✅ | 🔧 schema |
| geo:Province | class | ✅ | ❌ | · | ✅ covered |
| geo:isLocatedIn | property | ✅ | ✅ | · | ✅ covered |

### How to read this table

The **In input data**, **In SPARQL** and **In schema** columns show *where* a term is exercised, classifying every term into a role:

| Data | SPARQL | Schema | Role | Meaning |
|:---:|:---:|:---:|------|---------|
| ✅ | ✅ | | **fully exercised** | populated in the data *and* queried |
| ✅ | ❌ | | **data-only** | instances exist but no CQ asks about it — candidate for a new CQ |
| ❌ | ✅ | | **query-only** | matched by a query (e.g. via `rdfs:subClassOf*`) but never instantiated |
| ❌ | ❌ | ✅ | **schema** | not instantiated/queried, but structural — domain/range of a used property, superclass of a used class, or a metadata property (annotation/ontology property); good for documentation & inferencing; **excluded from coverage** |
| ❌ | ❌ | · | **unused** | declared but neither instantiated, queried, nor structurally referenced |

## Not used by any CQ

_none — every declared term is exercised or structural_

## Structural / schema terms (excluded from coverage)

Not directly exercised, but they define the schema of terms the CQs use:

- geo:Place (class) — domain of geo:isLocatedIn; range of geo:isLocatedIn; superclass of geo:AdministrativeDivision


## Per competency question

- **country-of-rotterdam.mustrd.ttl** — In which country is Rotterdam? — _passed_
  - in data:  geo:City, geo:Continent, geo:Country, geo:isLocatedIn
  - in query: geo:Country, geo:isLocatedIn
- **division-and-country-of-rotterdam.mustrd.ttl** — In what administrative division of what country is Rotterdam? — _passed_
  - in data:  geo:City, geo:Continent, geo:Country, geo:Province, geo:isLocatedIn
  - in query: geo:AdministrativeDivision, geo:Country, geo:isLocatedIn
