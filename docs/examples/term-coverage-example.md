<!--
  Example `--md` report for the ontology-term-coverage feature.
  Produced by running mustrd over a small geography ontology (declared via
  mustrdTest:hasOntologyPath) with two competency-question specs:
    pytest --mustrd --config=tests/mustrd-config.ttl --term-coverage --md=report.md
  The CQ table comes first; the Ontology term coverage section is appended.
  (file:// links are absolute on the machine that produced the report.)
-->
| Module | Class | Test | Competency Question | Status |
|--------|-------|------|---------------------|--------|
| mustrd-config.ttl | . | country-of-rotterdam.mustrd.ttl | In which country is Rotterdam? | passed |
| mustrd-config.ttl | . | division-and-country-of-rotterdam.mustrd.ttl | In what administrative division of what country is Rotterdam? | passed |


## Ontology term coverage

**Overall: 6/6 terms used to answer the CQs = 100%**

_(7 declared; 1 structural/schema term(s) excluded from the denominator — see below.)_


Ontology checked: [ontology/geography.ttl](file:///workspaces/training-data/geography-lab/ontology/geography.ttl)

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
| ❌ | ❌ | ✅ | **schema** | not instantiated/queried, but domain/range of a used property or superclass of a used class — good for documentation & inferencing; **excluded from coverage** |
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
