# ADR 0004: Why Multimethods

## Context
MustRD uses the `multimethods` library to implement multimethods, enabling dynamic dispatch based on argument types or values. This approach is inspired by Clojure's multimethods, which provide a flexible mechanism for dispatching functions based on custom criteria. In MustRD, multimethods are applied in several parts of the codebase, including:

1. **Table Result Comparison**: Dispatching methods for comparing table results based on expected and actual data.
2. **Specification Handling**: Combining specifications and retrieving spec components dynamically.
3. **Triplestore Integration**: Uploading "Given" data and running "When" actions for different triplestore types and SPARQL query types.

The decision to use multimethods was driven by the following considerations:

1. **Flexibility**: Multimethods allow dynamic handling of various input types and configurations without extensive conditional logic.
2. **Extensibility**: New triplestore types or query types can be added seamlessly by defining additional methods.
3. **Code Simplification**: Centralizing dispatch logic reduces code duplication and improves clarity.

## Decision
MustRD uses the `multimethods` library to implement multimethods for dynamic dispatch, leveraging their flexibility and extensibility.

## Consequences
- **Advantages**:
  - Simplifies code by reducing conditional logic.
  - Enhances extensibility for future triplestore types or query types.
  - Improves maintainability by centralizing dispatch logic.

- **Trade-offs**:
  - Multimethods may be unfamiliar to some Python developers, potentially impacting readability.
  - Dependency on the `multimethods` library adds complexity to the project.

- **Alternatives Considered**:
  - **Using Conditional Logic**: Approaches like `if-else` or `match` statements were deemed less maintainable and harder to extend. They require repetitive checks and are prone to errors when handling complex dispatch scenarios.
  - **Using Inheritance**: While inheritance allows for polymorphism, it introduces tight coupling between classes and can lead to rigid hierarchies. Multimethods, on the other hand, provide a more flexible and decoupled approach to dispatching behavior based on runtime criteria.
  - **Implementing Custom Dispatch Mechanisms**: This would require additional development effort and may lack the robustness and simplicity of a library like `multimethods`.

Multimethods were chosen for their ability to handle dynamic dispatch in a clean and extensible manner, avoiding the pitfalls of rigid class hierarchies and repetitive conditional logic.

## Future Considerations
- Provide documentation or examples to help developers understand the multimethods implementation.
- Evaluate the library's long-term support and compatibility with future Python versions.
