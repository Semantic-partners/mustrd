<!--
  Example output for the ontology-term-coverage proposal (docs/ontology-term-coverage.md).
  Generated from a small geography ontology (7 terms) with two competency-question
  specs. Reproduced here verbatim as an illustration of the proposed report.
-->
# Ontology term coverage — geography lab

**Overall: 6/7 terms used to answer the CQs = 86%**

A term is *used* if a CQ test exercises it — either in the **input data** (as an instance type or asserted predicate) or in the **SPARQL** query. Ontology declarations alone do not count.

Pass/fail gate: ON — only passing specs credited (from build/cq-coverage.md).


## Terms

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

The **In input data** and **In SPARQL** columns show *where* a term is exercised — together they classify every term into one of four roles, which is the real documentation value of this report:

| Data | SPARQL | Role | Meaning |
|:---:|:---:|------|---------|
| ✅ | ✅ | **fully exercised** | populated in the data *and* queried — the strongest evidence the term works |
| ✅ | ❌ | **data-only** | instances exist but no CQ asks about it — a candidate for a new competency question |
| ❌ | ✅ | **query-only** | matched by the query (e.g. via `rdfs:subClassOf*`) but never directly instantiated — relies on inference, not asserted data |
| ❌ | ❌ | **unused** | declared in the ontology but neither instantiated nor queried — dead weight until a CQ needs it |

## Not used by any CQ (declared but never exercised)

- geo:Place (class) — declared in the ontology, never instantiated in data nor referenced by a query

## Per competency question

- **country-of-rotterdam.mustrd.ttl** — In which country is Rotterdam? — _passed_
  - in data:  geo:City, geo:Continent, geo:Country, geo:isLocatedIn
  - in query: geo:Country, geo:isLocatedIn
- **division-and-country-of-rotterdam.mustrd.ttl** — In what administrative division of what country is Rotterdam? — _passed_
  - in data:  geo:City, geo:Continent, geo:Country, geo:Province, geo:isLocatedIn
  - in query: geo:AdministrativeDivision, geo:Country, geo:isLocatedIn
