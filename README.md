# mustrd

**"MustRD: Validate your SPARQL queries and transformations with precision and confidence, using BDD and Given-When-Then principles."**

[<img src="https://github.com/Semantic-partners/mustrd/raw/python-coverage-comment-action-data/badge.svg?sanitize=true" alt="coverage badge">](https://github.com/Semantic-partners/mustrd/tree/python-coverage-comment-action-data)

### Why?

SPARQL is a powerful query language for RDF data, but how can you ensure your queries and transformations are doing what you intend? Whether you're working on a pipeline or a standalone query, certainty is key.

While RDF and SPARQL offer great flexibility, we noticed a gap in tooling to validate their behavior. We missed the robust testing frameworks available in imperative programming languages that help ensure your code works as expected.

With MustRD, you can:

* Define data scenarios and verify that queries produce the expected results.
* Test edge cases to ensure your queries remain reliable.
* Isolate small SPARQL enrichment or transformation steps and confirm you're only inserting what you intend.

### What?

MustRD is a Spec-By-Example ontology with a reference Python implementation, inspired by tools like Cucumber. It uses the Given-When-Then approach to define and validate SPARQL queries and transformations.

MustRD is designed to be triplestore/SPARQL engine agnostic, leveraging open standards to ensure compatibility across different platforms.

### What it is NOT

MustRD is not an alternative to SHACL. While SHACL validates data structures, MustRD focuses on validating data transformations and query results.

### How?

You define your specs in Turtle (`.ttl`) or TriG (`.trig`) files using the Given-When-Then approach:

* **Given**: Define the starting dataset.
* **When**: Specify the action (e.g., a SPARQL query).
* **Then**: Outline the expected results.

Depending on the type of SPARQL query (CONSTRUCT, SELECT, INSERT/DELETE), MustRD runs the query and compares the results against the expectations defined in the spec.

Expectations can also be defined as:

* INSERT queries.
* SELECT queries.
* Higher-order expectation languages, similar to those used in various platforms.

### When?

MustRD is a work in progress, built to meet the needs of our projects across multiple clients and vendor stacks. While we find it useful, it may not meet your needs out of the box.

We invite you to try it, raise issues, or contribute via pull requests. If you need custom features, contact us for consultancy rates, and we may prioritize your request.

## Support

Semantic Partners is a specialist consultancy in Semantic Technology. If you need more support, contact us at info@semanticpartners.com or mustrd@semanticpartners.com.

