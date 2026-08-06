# ADR 0006: Type-Axis Dispatch Uses Multimethods

## Context
ADR 0004 records why the `multimethods` library is used in MustRD. This ADR is
narrower and normative: it names the axes that dispatch through multimethods and
why new branching on those axes should register a method rather than add a
conditional.

A handful of "axes" recur throughout the codebase, each a value that selects
behaviour:

- **triple store type** (`triple_store["type"]`) — RdfLib, GraphDb, Anzo, Stardog
- **SPARQL query type** (`when.queryType`) — Select, Construct, Update, …
- **spec component source + predicate** (`data_source_type`, `given`/`when`/`then`)
- **result type** (`SpecResult` subclass) — for rendering and classification

For each, one multimethod owns the dispatch table:

- `get_triple_store_config` — read a store's config by store type
- `upload_given` / `run_when_impl` — load data and run queries by store type
  (and query type); standard HTTP-SPARQL backends register through
  `register_sparql_http_backend`
- `get_spec_component` / `combine_specs` — build spec components by source type
- `render_result_diff` — render a result by result type

Adding a backend, query type, source or result type means registering a method.
That registration is slightly more ceremony than an `if` branch — and that
ceremony is the point. It keeps each axis's behaviour in one discoverable table
and makes the extension points explicit, rather than letting the same switch be
re-implemented ad hoc in several functions where the copies drift apart.

## Decision
Behaviour that varies along one of the axes above is expressed as a method on the
corresponding multimethod, not as an `if`/`elif`/`match` on the axis value.
Hand-rolled conditional dispatch on these axes is treated as an anti-pattern in
review.

A genuine exception: a *runtime precondition* that is not a dispatch key — for
example, "is the configured store actually Anzo?" checked inside a handler that
already dispatched on the spec's declared source. That stays a guard (see
`require_anzo`), because the configured store type is not the value the enclosing
multimethod dispatches on.

## Consequences
- **Advantages**:
  - One dispatch table per axis; extension points are explicit and discoverable.
  - Copies of the same switch cannot drift apart in separate functions.
  - Adding a backend/query type/source/result type is a local, additive change.
- **Trade-offs**:
  - Registering a method is more ceremony than a conditional, and multimethods
    are less familiar than `if`/`match` to some Python developers (see ADR 0004).
  - Dispatch is by value/type at runtime, so a missing method surfaces at call
    time via the `Default` handler rather than at import.
- **Alternatives Considered**:
  - *Conditional dispatch (`if`/`elif`/`match`) on the axis value*: reads as
    simpler in one function but reproduces the switch wherever the axis is
    handled, and those copies drift. This is the friction this ADR intentionally
    keeps.
  - *Class hierarchy / polymorphism*: viable for the result axis, but couples the
    data classes to concerns (rendering, comparison) that are cleaner kept out of
    them; see ADR 0004.

## Future Considerations
- The remaining hand-rolled conditionals on these axes (e.g. `check_result`'s
  choice of comparison and failure type, and pass/fail classification of results)
  are candidates to fold into multimethods as they are touched.
- The multimethod definitions link back to this ADR so the rule is visible at the
  point of change.
