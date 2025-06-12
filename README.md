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

## When?

MustRD is a work in progress, built to meet the needs of our projects across multiple clients and vendor stacks. While we find it useful, it may not meet your needs out of the box.

We invite you to try it, raise issues, or contribute via pull requests. If you need custom features, contact us for consultancy rates, and we may prioritize your request.

## Support

Semantic Partners is a specialist consultancy in Semantic Technology. If you need more support, contact us at info@semanticpartners.com or mustrd@semanticpartners.com.


