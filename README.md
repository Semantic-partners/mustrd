# MustRD

**"MustRD: Validate your SPARQL queries and transformations with precision and confidence, using BDD and Given-When-Then principles."**

[![Coverage Badge](https://github.com/Semantic-partners/mustrd/raw/python-coverage-comment-action-data/badge.svg?sanitize=true)](https://github.com/Semantic-partners/mustrd/tree/python-coverage-comment-action-data)

## Why?

SPARQL is a powerful query language for RDF data, but how can you ensure your queries and transformations are doing what you intend? Whether you're working on a pipeline or a standalone query, certainty is key.

While RDF and SPARQL offer great flexibility, we noticed a gap in tooling to validate their behavior. We missed the robust testing frameworks available in imperative programming languages that help ensure your code works as expected.

With MustRD, you can:

- Define data scenarios and verify that queries produce the expected results.
- Test edge cases to ensure your queries remain reliable.
- Isolate small SPARQL enrichment or transformation steps and confirm you're only inserting what you intend.

## What?

MustRD is a Spec-By-Example ontology with a reference Python implementation, inspired by tools like Cucumber. It uses the Given-When-Then approach to define and validate SPARQL queries and transformations.

MustRD is designed to be triplestore/SPARQL engine agnostic, leveraging open standards to ensure compatibility across different platforms.

### What it is NOT

MustRD is not an alternative to SHACL. While SHACL validates data structures, MustRD focuses on validating data transformations and query results.

## How?

You define your specs in Turtle (`.ttl`) or TriG (`.trig`) files using the Given-When-Then approach:

- **Given**: Define the starting dataset.
- **When**: Specify the action (e.g., a SPARQL query).
- **Then**: Outline the expected results.

Depending on the type of SPARQL query (CONSTRUCT, SELECT, INSERT/DELETE), MustRD runs the query and compares the results against the expectations defined in the spec.

Expectations can also be defined as:

- INSERT queries.
- SELECT queries.
- Higher-order expectation languages, similar to those used in various platforms.

## Example

### Configuration File

You'll have a configuration `.ttl` file, which acts as a suite of tests. It tells MustRD where to look for test specifications and any triplestore configurations you might have:

```ttl
:test_example a :MustrdTest;
              :hasSpecPath "test/specs/";
              :hasDataPath "test/data/";
              :hasPytestPath "example";
              :triplestoreSpecPath "test/triplestore_config/triplestores.ttl";
              :filterOnTripleStore triplestore:example_test .
```

### Test Specification

In the directory specified by `:hasSpecPath`, you'll have one or more `.mustrd.ttl` files. These can be organized in a directory structure. MustRD collects them and reports results to your test runner.

```ttl
:test_example :given [ a :FileDataset ;
                       :file "test/data/given.ttl" ] ;
              :when [ a :TextSparqlSource ;
                     :queryText "SELECT ?s ?p ?o WHERE { ?s ?p ?o }" ;
                     :queryType :SelectSparql ] ;
              :then [ a :OrderedTableDataset ;
                     :hasRow [ :variable "s" ; :boundValue "example:subject" ;
                               :variable "p" ; :boundValue "example:predicate" ;
                               :variable "o" ; :boundValue "example:object" ] ].
```

And you will have a `'test/data/given.ttl'` which contains the given ttl. 

```ttl
example:subject example:predicate example:object .
```

### Running Tests

Run the test using the MustRD Pytest plugin:

```bash
poetry run pytest --mustrd --config=test/mustrd_configuration.ttl --md=render/github_job_summary.md
```

This will validate your SPARQL queries against the defined dataset and expected results, ensuring your transformations behave as intended.

You can refer to SPARQL inline, in files, or in Anzo Graphmarts, Steps, or Layers. See `GETSTARTED.adoc` for more details.

#### What a run can produce

Every flag below works identically on `pytest --mustrd` and on `mustrd report`:

| Flag | You get | Detail |
| --- | --- | --- |
| *(none)* | pass/fail to the terminal | above |
| `--md=report.md` | Markdown summary, for a CI job summary or a PR comment | [Competency questions & coverage](#competency-questions--ontology-coverage) |
| `--viewer=report.html` | one self-contained HTML report — no server, no CDN | [The HTML report](#the-html-report) |
| `--cq` | competency-question table: which questions your tests answer | [Competency questions & coverage](#competency-questions--ontology-coverage) |
| `--term-coverage` | how much of your ontology the tests actually exercise | [Ontology term coverage](#ontology-term-coverage) |
| `--term-coverage-rdf=cov.ttl` | the same coverage as RDF (DQV + PROV) | [Ontology term coverage](#ontology-term-coverage) |
| `--results-rdf=run.ttl` | per-test results as RDF | [The HTML report](#the-html-report) |

```bash
# the usual pair: something to read in the terminal, something to attach to CI
pytest --mustrd --config=config.ttl --cq --term-coverage --md=report.md --viewer=report.html
```

`--viewer` already implies the coverage and competency-question graphs; `--cq` and
`--term-coverage` only affect the terminal and `--md` output.

#### Running on Windows

Windows is a supported, CI-tested platform — the matrix covers `windows-latest` on
Python 3.11, 3.12 and 3.13. Both front ends work the same as on Linux:

```powershell
pytest --mustrd --config=test\test_config_local.ttl --md=report.md
mustrd report --config test\test_config_local.ttl --viewer report.html
```

Two things differ in practice:

- **Non-ASCII output is handled for you.** The reports use `↳`, `▸`, `✅` and `❌`,
  and a Windows console still defaults to cp1252, where printing those raises
  `UnicodeEncodeError`. The CLI reconfigures its own streams to UTF-8 on startup, so
  this is not something you need to work around. If you drive mustrd from your own
  script and see an encoding error, `set PYTHONIOENCODING=utf-8` fixes it.
- **Paths in a config are resolved relative to the config file**, not the working
  directory, so backslashes and drive letters are fine and you can run from anywhere.

#### Running on locked-down Windows

Enterprise builds commonly block the bare `.exe` shims that pip installs into
`Scripts\`. The package installs fine, but the `mustrd` command won't start. Run the
module through the venv's interpreter instead:

```
python -m venv .venv
.venv/Scripts/python -m pip install mustrd

.venv/Scripts/python -m mustrd report --config config.ttl --viewer report.html
.venv/Scripts/python -m pytest --mustrd --config=config.ttl --md=report.md
```

`python -m mustrd` is exactly equivalent to the `mustrd` command — same entry point,
same flags. It exists for this.

#### Integrating with Visual Studio Code (vscode)
We have a pytest plugin.
1. Choose a python interpreter (probably a venv)
2. `pip install mustrd ` in it.
3. add to your settings.json
```json
    "python.testing.pytestArgs": [
        "--mustrd", "--md=junit/github_job_summary.md", "--config=test/test_config_local.ttl"
    ],
```
4. VS Code should auto discover your tests and they'll show up in the flask icon 'tab'.
![alt text](image.png)

Each `.mustrd.ttl` is a node in the tree, in the folder it actually lives in, with
one test under it per spec and triple store (`<spec>@<store>`). Running a single
one runs exactly that one. `:hasPytestPath` no longer shapes the tree — the
directories do — but it still filters, via `--pytest-path`.

#### Also worth installing: Mentor

If you are writing RDF in VS Code, get [**Mentor**](https://github.com/faubulous/mentor-vscode)
(`faubulous.mentor`, [mentor-vscode.dev](https://mentor-vscode.dev/), GPL-3.0). It is
the missing IDE for knowledge graphs, and it makes authoring mustrd specs markedly
less painful: syntax highlighting and validation for Turtle, TriG, N-Triples,
N-Quads, RDF/XML and SPARQL, browsable RDFS/OWL/SHACL/SKOS definition trees with
structural reasoning, workspace-wide autocomplete with prefix.cc lookup, go-to-definition
and cross-file references, prefix and IRI renaming, and a built-in triple store you
can run SPARQL against.

A mustrd spec is just Turtle, and Mentor treats it as such — jump straight from a
`must:fileurl` to the query it points at, or from a term in a spec to its definition
in your ontology. Nothing to configure on our side. Credit where it's due: it is an
excellent piece of work and not ours.

## Competency questions & ontology coverage

A competency question (CQ) is a first-class `cq:CompetencyQuestion` node (its
vocabulary is `cq:` = `https://mustrd.org/competencyQuestion/`) — it owns the
question (`cq:question`, a sub-property of `rdfs:label`) and *optionally* links
to the test(s) that answer it with `cq:cqSpec`. CQ nodes live in any
`.mustrd.ttl` in the suite:

```ttl
@prefix cq: <https://mustrd.org/competencyQuestion/> .

:rotterdamCountryCQ a cq:CompetencyQuestion ;
    cq:question "In which country is Rotterdam?" ;
    cq:cqSpec :test_example .        # optional — omit for a CQ with no test yet
```

Because the link is optional, you can record a CQ *before* writing its test; the
report lists such CQs as gaps (Test column "—").

Two opt-in report flags build on this, and compose:

- **`--cq`** adds a **Competency Questions** table (one row per CQ node — its
  linked test(s) and status) and a per-CQ breakdown. Needs no ontology.
- **`--term-coverage`** adds **ontology term coverage over all mustrd tests**
  (see below). Needs an ontology.

Plain `--md` (neither flag) is unchanged: it still writes the standard
test-results summary.

```bash
pytest --mustrd --config=config.ttl --md=report.md            # test-results summary
pytest --mustrd --config=config.ttl --cq --md=report.md       # + competency questions
```

### Ontology term coverage

`--term-coverage` reports **how much of your ontology your tests actually
exercise** — an overall percentage and a per-term table (to stdout, and the
`--md` file if given). Add `--cq` too and it also shows how much is backed by a
*competency question* (a stricter number) via a `CQ Term Coverage` column.

Tell MustRD which ontology to measure against with `:hasOntologyPath` in your
config — a file or a directory (scanned recursively), repeatable:

```ttl
:myTest a :MustrdTest ;
    :hasSpecPath     "specs/" ;
    :hasDataPath     "data/" ;
    :hasOntologyPath "ontology/" ;   # file or directory; repeat for several
    :filterOnTripleStore triplestore:RdfLib .
```

```bash
pytest --mustrd --config=config.ttl --term-coverage             # coverage to stdout
pytest --mustrd --config=config.ttl --term-coverage --cq --md=report.md
```

(If `--term-coverage` is set without `:hasOntologyPath`, MustRD fails early and
tells you exactly what to add.)

Coverage is **data-based**: a declared term counts as **covered** when a
*passing* test **populates it in input data** (as an instance type or asserted
predicate) — whether or not a query also names it. A term named *only* in a
query but never instantiated is **query-only** and does *not* count (the test
passes without it); it's often a sign a TBox axiom belongs in the ontology, not
the fixture — the report flags those under **⚠️ TBox axioms in test data**.
Terms that are only structurally referenced (the `rdfs:domain`/`rdfs:range` of a
used property, a superclass of a used class, or a metadata property such as an
`owl:AnnotationProperty`/`owl:OntologyProperty`) are reported separately as
**structural** terms and excluded from the percentage. Every term is classified
as *fully exercised*, *data-only*, *query-only*, *structural*, or *unused* — so
untested terms surface immediately. When you pass `--md`, the parent directory is
created automatically if it doesn't exist.

**RDF output.** `--term-coverage-rdf=coverage.ttl` writes the result as RDF (W3C
DQV + PROV) for a knowledge graph: quality measurements `computedOn` the ontology
IRI and its `owl:versionIRI` (value a decimal ratio), a per-term breakdown, and
quality issues — all with stable IRIs, no blank nodes.

See [`docs/ontology-term-coverage.md`](docs/ontology-term-coverage.md) for the
full definition and [`docs/examples/geography-example/report/term-coverage-example.md`](docs/examples/geography-example/report/term-coverage-example.md)
for sample output.

## The HTML report

`--viewer=report.html` writes **one self-contained HTML file**: no build step, no
CDN, no server. It carries the run's RDF, a Turtle parser and
[VanJS](https://vanjs.org) (~5KB, MIT, vendored inline), and builds
everything in the browser — a pass/fail/skip test tree with timings, the term
coverage table (classes nested by `rdfs:subClassOf`, properties under their
`rdfs:domain`), the competency questions, and the quality issues. Attach it to a
CI run, email it, or open it from disk.

```bash
pytest --mustrd --config=config.ttl --viewer=report.html
```

`--viewer` implies the coverage and competency-question graphs, so you don't need
`--term-coverage`/`--cq` as well (they only affect the terminal and `--md`
output). Coverage appears whenever the config declares `:hasOntologyPath`.

**Sources are embedded.** By default each spec's Turtle and the SPARQL it ran are
inlined into the page, syntax-highlighted, so the report is readable without the
files it was generated from — a path in a graph only resolves from the directory
the run happened in, which is no use in an emailed file or a CI artifact. Any file
reference in the report opens the embedded copy in place. `--no-viewer-sources`
turns this off for a smaller page.

The page is also a viewer for *any* mustrd graph: drop a `.ttl` or `.jsonld` from
`--term-coverage-rdf` / `--results-rdf` onto it, or point it at one with
`?ttl=path/to/run.ttl`. Drop several to compare or merge runs.

Related flags: `--results-rdf` / `--results-jsonld` write the per-test results
graph (every test, `passed`/`failed`/`skipped`, with timing) on its own;
`--term-coverage-jsonld` writes the coverage graph as JSON-LD. `--viewer-title`
sets the page title, and `--viewer-src-base` prefixes the page's source-file
links when it is served from somewhere other than the working directory.

[Live example report](https://mustrd.org/examples/geography-example/report/).

## The `mustrd` CLI

The pytest plugin is a front end, not the engine. Spec execution
(`mustrd.runner`) and reporting (`mustrd.reporting`) are plain libraries, and the
`mustrd` command drives them **without pytest** — same config file, same specs,
same reports:

```bash
mustrd run    --config config.ttl                      # run the specs, review results
mustrd report --config config.ttl --viewer report.html  # run + emit the reports
```

`config.ttl` is your own MustrdTest configuration — the same file `pytest
--mustrd --config=` takes. To try it against the worked example in this repo:

```bash
mustrd report --config docs/examples/geography-example/mustrd-config.ttl \
              --viewer report.html
```

Paths inside a config are resolved relative to *the config file*, so it can be
run from anywhere; the viewer's source links are relative to the working
directory (see `--viewer-src-base`).

`mustrd report` takes the same reporting flags as the plugin (`--md`,
`--term-coverage`, `--cq`, `--term-coverage-rdf`, `--results-rdf`, `--viewer`, …)
plus `--ontology` to override `:hasOntologyPath`. Both exit non-zero if any spec
does not pass.

## When?

MustRD is a work in progress, built to meet the needs of our projects across multiple clients and vendor stacks. While we find it useful, it may not meet your needs out of the box.

We invite you to try it, raise issues, or contribute via pull requests. If you need custom features, contact us for consultancy rates, and we may prioritize your request.

Contributing: see [CONTRIBUTING.md](CONTRIBUTING.md) for setup, the two test suites, and the traps.

## Releasing

Maintainers: releases are cut by pushing a version tag (`git tag 0.7.5 && git push origin 0.7.5`). See [RELEASING.md](RELEASING.md) for the full flow, including beta/candidate releases.

## Support

Semantic Partners is a specialist consultancy in Semantic Technology. If you need more support, contact us at info@semanticpartners.com or mustrd@semanticpartners.com.


