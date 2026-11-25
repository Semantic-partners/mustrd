# ADR 0007: Specs Written in Pytest

## Context
ADR 0003 makes Turtle the format for specs. Some suites want a spec in code instead:
the question, the test data, the query and the expected answer together in one pytest
test, with small inline test data per question. Before this, such a suite had to set
the plugin's internal `item.spec` record itself and write a competency question file
for `--cq`. That is an undocumented contract.

The alternatives were weaker: generating `.mustrd.ttl` from the tests runs every spec
twice under `pytest --mustrd`, and `mustrd coverage` credits every spec as passing
without running it.

## Decision
`mustrd.pytest_spec` provides a `mustrd_spec` fixture (`cq`, `given`, `when`, `then`),
registered as its own pytest plugin. It fills the same `spec` record the plugin
already reads for coverage, plus the competency questions the test links, which the
plugin adds to those from the spec files.

Specs in code complement Turtle specs; they do not replace them.

## Consequences
- A spec in code runs once, and counts towards coverage only when it passes. Static
  coverage (`mustrd coverage`, `--coverage-only`) runs no tests, so it leaves these specs out.
- No competency question file is needed for these specs.
- Only SELECT queries, run on rdflib against the given data. Other spec types and
  triple stores remain Turtle-only.
- The `spec` record is now a public contract: changing its fields breaks specs in code.
- A config still needs `:hasSpecPath`, even when every spec lives in code.
