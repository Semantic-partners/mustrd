<!--
  Example `--md` report for the ontology-term-coverage feature.
  Produced by running mustrd over a small geography ontology (7 terms) with two
  competency-question specs:
    pytest --mustrd --config=tests/mustrd-config.ttl --md=report.md
  The CQ table comes first; the Ontology term coverage section is appended.
  Reproduced here verbatim as documentation.
-->
| Module | Class | Test | Competency Question | Status |
|--------|-------|------|---------------------|--------|
| mustrd-config.ttl | . | country-of-rotterdam.mustrd.ttl | In which country is Rotterdam? | passed |
| mustrd-config.ttl | . | division-and-country-of-rotterdam.mustrd.ttl | In what administrative division of what country is Rotterdam? | passed |


## Ontology term coverage

**Overall: 6/7 terms used to answer the CQs = 86%**

A term is *used* if a passing CQ test exercises it — either in the **input data** (as an instance type or asserted predicate) or in the **SPARQL** query. Ontology declarations alone do not count.

| Term | Kind | In input data | In SPARQL | Used |
|------|------|:---:|:---:|:---:|
| geo:AdministrativeDivision | class | ❌ | ✅ | ✅ |
| geo:City | class | ✅ | ❌ | ✅ |
| geo:Continent | class | ✅ | ❌ | ✅ |
| geo:Country | class | ✅ | ✅ | ✅ |
| geo:Place | class | ❌ | ❌ | ❌ |
| geo:Province | class | ✅ | ❌ | ✅ |
| geo:isLocatedIn | property | ✅ | ✅ | ✅ |

### How to read this table

The **In input data** and **In SPARQL** columns show *where* a term is exercised — together they classify every term into one of four roles:

| Data | SPARQL | Role | Meaning |
|:---:|:---:|------|---------|
| ✅ | ✅ | **fully exercised** | populated in the data *and* queried |
| ✅ | ❌ | **data-only** | instances exist but no CQ asks about it — candidate for a new CQ |
| ❌ | ✅ | **query-only** | matched by a query (e.g. via `rdfs:subClassOf*`) but never instantiated |
| ❌ | ❌ | **unused** | declared but neither instantiated nor queried |

## Not used by any CQ

- geo:Place (class) — declared in the ontology, never instantiated in data nor referenced by a query


## Per competency question

- **country-of-rotterdam.mustrd.ttl** — In which country is Rotterdam? — _passed_
  - in data:  geo:City, geo:Continent, geo:Country, geo:isLocatedIn
  - in query: geo:Country, geo:isLocatedIn
- **division-and-country-of-rotterdam.mustrd.ttl** — In what administrative division of what country is Rotterdam? — _passed_
  - in data:  geo:City, geo:Continent, geo:Country, geo:Province, geo:isLocatedIn
  - in query: geo:AdministrativeDivision, geo:Country, geo:isLocatedIn
