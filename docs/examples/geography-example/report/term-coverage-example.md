# Ontologies Report

## Coverage Report

### Ontologies

Coverage below is measured against these ontologies:

- [ontology/place.ttl](../ontology/place.ttl) — `http://example.org/place#` — A minimal vocabulary for places and how they are geographically contained within one another.
- [ontology/governance.ttl](../ontology/governance.ttl) — `http://example.org/governance#` — A tiny vocabulary for governance roles and the places they govern.


### Term Coverage

**Overall: 8/9 terms exercised by the tests = 89%**

**By a competency question: 7/9 = 78%**


_(11 declared; 2 structural term(s) excluded from the denominator — see below.)_

A term counts as **covered** when a passing test **populates it in input data** (as an instance type or asserted predicate) — whether or not a query also names it. A term named *only* in a query but never instantiated is **not** covered (the test can still pass without it); it is flagged **query-only**. Ontology declarations alone never count.

Classes are arranged by `rdfs:subClassOf` (indented `↳` under their superclass); a class's properties sit beneath it (`▸`, by `rdfs:domain`).

| Term | Kind | <abbr title="A passing test asserts the term in its given data — as an rdf:type object or an asserted predicate">In input data</abbr> | <abbr title="A passing test's SPARQL query names the term as an IRI (from the parsed query algebra; comments ignored)">In SPARQL</abbr> | <abbr title="Not instantiated or queried, but load-bearing: domain/range of a used property, superclass of a used class, or a metadata property. Excluded from the coverage %">Structural</abbr> | <abbr title="covered = populated in a passing test's input data; query-only = named by a query but never instantiated (not covered); structural = excluded; unused = untouched">Test Term Coverage</abbr> | <abbr title="Whether a competency question — not just any test — exercises the term">CQ Term Coverage</abbr> |
|------|------|:---:|:---:|:---:|:---:|:---:|
| foaf:Person · _external_ | class | ❌ | ❌ | ✅ | 🔧 structural | 🔧 structural |
| &nbsp;&nbsp;&nbsp;&nbsp;▸ gov:governs | property | ✅ | ✅ | · | ✅ covered | ✅ |
| &nbsp;&nbsp;&nbsp;&nbsp;↳ gov:Mayor | class | ✅ | ✅ | · | ✅ covered | ✅ |
| place:Place | class | ❌ | ❌ | ✅ | 🔧 structural | 🔧 structural |
| &nbsp;&nbsp;&nbsp;&nbsp;▸ place:isLocatedIn | property | ✅ | ✅ | · | ✅ covered | ✅ |
| &nbsp;&nbsp;&nbsp;&nbsp;↳ place:AdministrativeDivision | class | ❌ | ✅ | · | ❌ query only | ❌ |
| &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;↳ place:Province | class | ✅ | ❌ | · | ✅ covered | ✅ |
| &nbsp;&nbsp;&nbsp;&nbsp;↳ place:City | class | ✅ | ✅ | · | ✅ covered | ✅ |
| &nbsp;&nbsp;&nbsp;&nbsp;↳ place:Continent | class | ✅ | ❌ | · | ✅ covered | ✅ |
| &nbsp;&nbsp;&nbsp;&nbsp;↳ place:Country | class | ✅ | ✅ | · | ✅ covered | ✅ |
| &nbsp;&nbsp;&nbsp;&nbsp;↳ place:Region | class | ✅ | ✅ | · | ✅ covered | ❌ unused by CQ — exercised by [region-lookup.mustrd.ttl](../specs/region-lookup.mustrd.ttl) (data & SPARQL) |
| place:basedOnStandard | property | ❌ | ❌ | ✅ | 🔧 structural | 🔧 structural |

#### How to read this table

The **In input data**, **In SPARQL** and **Structural** columns show *where* a term is exercised, classifying every term into a role. **Coverage is data-based**: a term must be populated in some passing test's input data to count.

| Data | SPARQL | Structural | Role | Counts? |
|:---:|:---:|:---:|------|---------|
| ✅ | ✅ | | **fully exercised** | ✅ **covered** — populated in the data *and* queried (strongest evidence) |
| ✅ | ❌ | | **data-only** | ✅ **covered** — instances exist; a property-path query may consume them by IRI without naming the class (to be confirmed by mutation testing). Candidate for a dedicated query. |
| ❌ | ✅ | | **query-only** | ❌ **not covered** — matched by a query (e.g. via `rdfs:subClassOf*`) but never instantiated; the test can pass without it. Often a sign the query leans on a TBox axiom that belongs in the ontology. |
| ❌ | ❌ | ✅ | **structural** | 🔧 **excluded** — not instantiated/queried, but load-bearing: domain/range of a used property, superclass of a used class, or a metadata property (annotation/ontology property). Good for documentation & inferencing. |
| ❌ | ❌ | | **unused** | ❌ **not covered** — not exercised by any test, nor structural to one |

**CQ Term Coverage** shows whether a *competency question* (not just any test) exercises the term: ✅ yes, ❌ covered only by non-CQ tests (so it lacks CQ coverage), 🔧 structural (excluded, so not applicable).

### Not covered by any test

- place:AdministrativeDivision (class) — **query-only**: named by a query but never populated in any test's input data, so the test passes without it (consider moving the enabling TBox axiom into the ontology)


### Structural terms (excluded from coverage)

Not directly exercised, but load-bearing — they define the structure of the terms the tests use:

- place:Place (class) — domain of place:isLocatedIn; range of place:isLocatedIn; superclass of place:AdministrativeDivision
- place:basedOnStandard (property) — ontology property


### ⚠️ Used but not declared

Referenced by a test, and in an ontology's namespace, but **not declared** in any loaded ontology — a likely typo or a missing definition:

- **gov:appointedOn**
  - [mayor-of-rotterdam.mustrd.ttl](../specs/mayor-of-rotterdam.mustrd.ttl) — SPARQL

- **place:hasEconomicArea**
  - [country-of-rotterdam.mustrd.ttl](../specs/country-of-rotterdam.mustrd.ttl) — input data


### ⚠️ TBox axioms in test data

These tests define ontology structure (class/property declarations, `rdfs:subClassOf`/`domain`/`range`) in their **input data**. A `given` should hold *instance* data — schema belongs in the ontology. If a query only matches through one of these axioms (e.g. a `rdfs:subClassOf*` path), that is why the term shows as **query-only** rather than covered. Consider moving them into an ontology loaded via `:hasOntologyPath`:

- [division-and-country-of-rotterdam.mustrd.ttl](../specs/division-and-country-of-rotterdam.mustrd.ttl)
  - `place:Province a owl:Class`
  - `place:Province rdfs:subClassOf place:AdministrativeDivision`


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

- place:AdministrativeDivision (class) — not covered by any competency question; a CQ query names it but no CQ populates it in data (**query-only**)
- place:Region (class) — not covered by any competency question; covered by [region-lookup.mustrd.ttl](../specs/region-lookup.mustrd.ttl) (data & SPARQL)


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
