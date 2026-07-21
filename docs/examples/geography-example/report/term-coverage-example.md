# Ontologies Report

## Ontologies

Coverage below is measured against this ontology:

- [docs/examples/geography-example/ontology/geography.ttl](../ontology/geography.ttl) — `http://example.org/place#` — A minimal vocabulary for places and how they are geographically contained within one another.


## Competency Questions

| Module | Class | Test | Competency Question | Status |
|--------|-------|------|---------------------|--------|
| docs/examples/geography-example/mustrd-config.ttl | rdflib | [country-of-rotterdam.mustrd.ttl](../specs/country-of-rotterdam.mustrd.ttl) | In which country is Rotterdam? | passed |
| docs/examples/geography-example/mustrd-config.ttl | rdflib | [division-and-country-of-rotterdam.mustrd.ttl](../specs/division-and-country-of-rotterdam.mustrd.ttl) | In what administrative division of what country is Rotterdam? | passed |


## Ontology term coverage

**Overall: 6/6 terms used to answer the CQs = 100%**

_(8 declared; 2 structural/schema term(s) excluded from the denominator — see below.)_

A term is *used* if a passing CQ test exercises it — either in the **input data** (as an instance type or asserted predicate) or in the **SPARQL** query. Ontology declarations alone do not count.

| Term | Kind | In input data | In SPARQL | In schema | Status |
|------|------|:---:|:---:|:---:|:---:|
| place:AdministrativeDivision | class | ❌ | ✅ | · | ✅ covered |
| place:City | class | ✅ | ❌ | · | ✅ covered |
| place:Continent | class | ✅ | ❌ | · | ✅ covered |
| place:Country | class | ✅ | ✅ | · | ✅ covered |
| place:Place | class | ❌ | ❌ | ✅ | 🔧 schema |
| place:Province | class | ✅ | ❌ | · | ✅ covered |
| place:basedOnStandard | property | ❌ | ❌ | ✅ | 🔧 schema |
| place:isLocatedIn | property | ✅ | ✅ | · | ✅ covered |

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

- place:Place (class) — domain of place:isLocatedIn; range of place:isLocatedIn; superclass of place:AdministrativeDivision
- place:basedOnStandard (property) — ontology property


## Per competency question

- **country-of-rotterdam.mustrd.ttl** — In which country is Rotterdam? — _passed_
  - in data:  place:City, place:Continent, place:Country, place:isLocatedIn
  - in query: place:Country, place:isLocatedIn
- **division-and-country-of-rotterdam.mustrd.ttl** — In what administrative division of what country is Rotterdam? — _passed_
  - in data:  place:City, place:Continent, place:Country, place:Province, place:isLocatedIn
  - in query: place:AdministrativeDivision, place:Country, place:isLocatedIn
