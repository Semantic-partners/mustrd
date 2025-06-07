# ADR 0002: Why Pytest Plugin

## Context
MustRD integrates with Pytest as a plugin to facilitate testing of SPARQL queries and transformations. The decision to use Pytest was based on the following considerations:

1. **Popularity**: Pytest is one of the most widely-used testing frameworks in Python, ensuring familiarity for developers.
2. **Extensibility**: Pytest's plugin architecture allows MustRD to seamlessly integrate custom functionality.
3. **Ease of Use**: Pytest provides a simple and intuitive interface for writing and running tests.
4. **Rich Features**: Pytest supports fixtures, parameterized tests, and detailed reporting, which are essential for MustRD's testing needs.

## Decision
MustRD was implemented as a Pytest plugin to leverage its popularity, extensibility, and rich feature set.

## Consequences
- Developers can use MustRD alongside their existing Pytest workflows.
- Pytest's ecosystem provides additional tools and plugins that enhance testing capabilities.
- The dependency on Pytest may limit adoption by teams using other testing frameworks, but this trade-off is acceptable given Pytest's widespread use in the Python community.
- Pytest plugins integrate seamlessly with development environments like VS Code and IntelliJ/PyCharm, providing a user-friendly interface and streamlined developer experience with minimal setup effort.
- This integration does not preclude the possibility of adding support for other testing frameworks or development environments in the future.
