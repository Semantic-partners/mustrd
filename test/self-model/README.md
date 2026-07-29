# Competency questions over mustrd's own model

mustrd measuring itself: how much of `mustrd/model/ontology.ttl` do its own specs
exercise, and which questions about a spec can the model actually answer?

```bash
pytest --mustrd --config=test/test_config_self_model.ttl \
       --pytest-path=self_model --term-coverage --cq
```

Run it from the repo root, and **without a path argument** — passing one (say
`test/self-model`) collects nothing, runs zero specs and reports 0% rather than
failing, which reads as bad coverage instead of no run. `--pytest-path` is the
filter that works.

## The trick: a spec file *as data*

mustrd's vocabulary is used declaratively. A spec **is** `must:TestSpec`,
`must:given`, `must:when` — it never asks *about* them. So nothing queries `must:`
terms, and coverage over mustrd's own model would be zero by construction.

Unless a spec reads a spec file as its input. That is what these do:
`data/a-spec.ttl` is a mustrd spec, and each spec here takes it as `must:given` and
queries it with SPARQL over `must:` terms. The competency questions are then real
questions about the model —

- What SPARQL does a spec run, and of what query type?
- Where does a spec get its input data, and what kind of dataset is it?
- How does a spec state what it expects, and which variables does it bind?

— and each is answered by a passing test, which is the whole claim a competency
question makes.

## Why the number does not move when you add a question

Coverage counts a term as **covered** when a passing test *populates it in input
data*. Every spec here reads the same `data/a-spec.ttl`, so the covered set is
determined by **what the fixture contains**, not by how many questions query it.
Three CQs and two report the same 17/63 as one would.

To move it, enrich the fixture: a spec using `must:UpdateSparql`, an
`must:OrderedTableDataset`, an Anzo source, `must:hasBinding` on a `when` rather
than a `then`. Each variety of spec you add to `data/a-spec.ttl` puts more of the
model into input data, and the percentage follows. Adding queries adds *answers*,
not coverage.

## Why the fixture is not a real suite spec

Copying a file from `test-specs/` would be truer dogfooding, and it would break
these tests the moment somebody edited that file for unrelated reasons — the
expected results here are exact. So the fixture is purpose-built, and named `.ttl`
rather than `.mustrd.ttl` so no spec collection ever picks it up as a spec to run.

Pointing this at the real spec corpus is the obvious next step, and wants
assertions that do not pin exact rows — a count, or an ASK.

## Why it needs its own config

`test_config_self_model.ttl` is separate from `test_config_local.ttl` so the main
suite's numbers are untouched. This is the one run where `mustrd/model/ontology.ttl`
is the *subject*; everywhere else it is the vocabulary specs are written in, and
`WELL_KNOWN` in `mustrd/ontology.py` correctly filters it out. A namespace a graph
declares as its own (`owl:Ontology`) counts as measurable — see
`test/test_own_vocabulary_coverage.py`.
