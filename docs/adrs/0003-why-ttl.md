# ADR 0003: Why TTL

## Context
MustRD uses Turtle (TTL) files for defining specifications. Turtle is a compact and human-readable syntax for RDF data. Unlike classic BDD Given-When-Then files that rely on regex matching, MustRD adopts TTL files for the following reasons:

1. **Structured Data**: TTL files provide a formal structure for defining specifications, avoiding the ambiguity and potential errors associated with regex-based parsing.
2. **Semantic Clarity**: By leveraging RDF's semantic capabilities, TTL files enable precise representation of data and relationships, which is critical for SPARQL query validation.
3. **Tool Compatibility**: TTL files are compatible with a wide range of RDF tools and libraries, facilitating integration and interoperability.
4. **Ease of Maintenance**: Maintaining TTL files is simpler compared to regex-based BDD files, as changes can be made without worrying about breaking regex patterns.
5. **Scalability**: TTL files scale better for complex specifications, allowing hierarchical and interconnected data structures that are difficult to achieve with regex-based approaches.
6. **Avoiding Facades**: Classic BDD frameworks often create what appears to be a pseudo-executable language in semi-English, maintained by extensive regex matching. Since MustRD operates purely in data terms, this facade is unnecessary, and TTL provides a more direct and efficient approach.

## Decision
MustRD uses TTL files for defining specifications to leverage their readability, standardization, and ease of integration.

## Consequences
- Developers and domain experts can easily create and modify specifications.
- The use of a standardized format ensures compatibility with existing RDF tools.
- TTL's compact syntax reduces the complexity of working with RDF data.
- TTL, like other RDF serialization formats, lacks native support for ordered lists, which can make representing sequences or hierarchies cumbersome.
- This limitation may require additional workarounds, such as using custom predicates or external tools, to maintain order in data.
- Developers may find it challenging to work with complex specifications that rely on ordered data.
- Pairing TTL files with the VS Code plugin "faubulous.mentor" by an SP consultant provides a pleasant code navigation experience, enhancing productivity and ease of use.
