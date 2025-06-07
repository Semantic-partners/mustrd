# ADR 0001: Why Python

## Context
MustRD is implemented in Python, a versatile and widely-used programming language. The choice of Python was driven by several factors:

1. **Ease of Use**: Python's syntax is simple and readable, making it accessible to developers with varying levels of experience.
2. **Rich Ecosystem**: Python has a vast library ecosystem, including RDF and SPARQL-related libraries like `rdflib` and `pyshacl`, which are essential for MustRD's functionality.
3. **Community Support**: Python has a large and active community, ensuring robust support and resources for development.
4. **Cross-Platform Compatibility**: Python runs on all major operating systems, making MustRD accessible to a wide audience.

## Decision
Python was chosen as the implementation language for MustRD to leverage its simplicity, ecosystem, and community support.

## Consequences
- Developers familiar with Python can easily contribute to MustRD.
- The rich library ecosystem accelerates development and reduces the need for custom implementations.
- Python's performance may not match lower-level languages, but this trade-off is acceptable given the project's focus on usability and flexibility.
