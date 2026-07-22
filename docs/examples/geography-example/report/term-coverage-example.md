# Ontologies Report

## Coverage Report

### Ontologies

Coverage below is measured against these ontologies:

- [ontology/place.ttl](../ontology/place.ttl) — `http://example.org/place#` — A minimal vocabulary for places and how they are geographically contained within one another.
- [ontology/governance.ttl](../ontology/governance.ttl) — `http://example.org/governance#` — A tiny vocabulary for governance roles and the places they govern.


### Term Coverage

**Overall: 9/9 terms exercised by the tests = 100%**

**By a competency question: 8/9 = 89%**


_(11 declared; 2 structural/schema term(s) excluded from the denominator — see below.)_

A term is *used* if a passing test exercises it — either in the **input data** (as an instance type or asserted predicate) or in its **SPARQL** query. Ontology declarations alone do not count.

| Term | Kind | In input data | In SPARQL | In schema | Test Coverage | By a CQ? |
|------|------|:---:|:---:|:---:|:---:|:---:|
| gov:Mayor | class | ✅ | ✅ | · | ✅ covered | ✅ |
| place:AdministrativeDivision | class | ❌ | ✅ | · | ✅ covered | ✅ |
| place:City | class | ✅ | ✅ | · | ✅ covered | ✅ |
| place:Continent | class | ✅ | ❌ | · | ✅ covered | ✅ |
| place:Country | class | ✅ | ✅ | · | ✅ covered | ✅ |
| place:Place | class | ❌ | ❌ | ✅ | 🔧 schema | 🔧 schema |
| place:Province | class | ✅ | ❌ | · | ✅ covered | ✅ |
| place:Region | class | ✅ | ✅ | · | ✅ covered | ❌ unused by CQ — exercised by [region-lookup.mustrd.ttl](../specs/region-lookup.mustrd.ttl) (data & SPARQL) |
| gov:governs | property | ✅ | ✅ | · | ✅ covered | ✅ |
| place:basedOnStandard | property | ❌ | ❌ | ✅ | 🔧 schema | 🔧 schema |
| place:isLocatedIn | property | ✅ | ✅ | · | ✅ covered | ✅ |

#### How to read this table

The **In input data**, **In SPARQL** and **In schema** columns show *where* a term is exercised, classifying every term into a role:

| Data | SPARQL | Schema | Role | Meaning |
|:---:|:---:|:---:|------|---------|
| ✅ | ✅ | | **fully exercised** | populated in the data *and* queried |
| ✅ | ❌ | | **data-only** | instances exist but no test queries it — candidate for a new query |
| ❌ | ✅ | | **query-only** | matched by a query (e.g. via `rdfs:subClassOf*`) but never instantiated |
| ❌ | ❌ | ✅ | **schema** | not instantiated/queried, but structural — domain/range of a used property, superclass of a used class, or a metadata property (annotation/ontology property); good for documentation & inferencing; **excluded from coverage** |
| ❌ | ❌ | | **unused** | not exercised by any test, nor structural to one |

**By a CQ?** shows whether a *competency question* (not just any test) exercises the term: ✅ yes, ❌ covered only by non-CQ tests (so it lacks CQ coverage), 🔧 schema (excluded, so not applicable).

### Not used by any test

_none — every declared term is exercised or structural_

### Structural / schema terms (excluded from coverage)

Not directly exercised, but they define the schema of terms the tests use:

- place:Place (class) — domain of place:isLocatedIn; range of place:isLocatedIn; superclass of place:AdministrativeDivision
- place:basedOnStandard (property) — ontology property


### ⚠️ Used but not declared

Referenced by a test, and in an ontology's namespace, but **not declared** in any loaded ontology — a likely typo or a missing definition:

- **gov:appointedOn**
  - [mayor-of-rotterdam.mustrd.ttl](../specs/mayor-of-rotterdam.mustrd.ttl) — SPARQL

- **place:hasEconomicArea**
  - [country-of-rotterdam.mustrd.ttl](../specs/country-of-rotterdam.mustrd.ttl) — input data


## Competency Questions Report

### Competency Questions

#### [mustrd-config.ttl](../mustrd-config.ttl) — rdflib

_3 of 4 tests are competency questions._

| Competency Question | Test | Test Status | Coverage Status |
|---------------------|------|-------------|-----------------|
| In which country is Rotterdam? | [country-of-rotterdam.mustrd.ttl](../specs/country-of-rotterdam.mustrd.ttl) | ✅ passed | ⚠️ undeclared: place:hasEconomicArea (input data) |
| In what administrative division of what country is Rotterdam? | [division-and-country-of-rotterdam.mustrd.ttl](../specs/division-and-country-of-rotterdam.mustrd.ttl) | ✅ passed | ✅ passed |
| Who is the mayor of Rotterdam? | [mayor-of-rotterdam.mustrd.ttl](../specs/mayor-of-rotterdam.mustrd.ttl) | ✅ passed | ⚠️ undeclared: gov:appointedOn (SPARQL) |



### Not used by any CQ

- place:Region (class) — not exercised by any competency question (a non-CQ test may still use it)


### Per competency question

🧩 **requires ontology to pass** marks a CQ whose query only matches its data through the ontology's class hierarchy (it queries a class but the data holds instances of a *subclass*), so the ontology must be loaded as an input dataset for the test to pass.


- **country-of-rotterdam.mustrd.ttl** — In which country is Rotterdam? — _passed_
  - in data:  place:City, place:Continent, place:Country, place:isLocatedIn
  - in query: place:Country, place:isLocatedIn

- **division-and-country-of-rotterdam.mustrd.ttl** — In what administrative division of what country is Rotterdam? — _passed_ — 🧩 **requires ontology to pass**
  - in data:  place:City, place:Continent, place:Country, place:Province, place:isLocatedIn
  - in query: place:AdministrativeDivision, place:Country, place:isLocatedIn

- **mayor-of-rotterdam.mustrd.ttl** — Who is the mayor of Rotterdam? — _passed_
  - in data:  gov:Mayor, gov:governs, place:City
  - in query: gov:Mayor, gov:governs, place:City
