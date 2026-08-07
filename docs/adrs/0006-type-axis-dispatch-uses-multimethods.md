# ADR 0006: Type-Axis Dispatch Uses Multimethods

## Context
ADR 0004 records why the `multimethods` library is in MustRD. This ADR is
narrower: it records *what the pattern is for here* and *when to reach for it* —
because the honest justification is not the one usually given ("copies drift").

The original motivation was supporting a new triple store as one cohesive slice.
SPARQL is a standard, but stores vary in awkward, non-uniform ways — endpoint/URL
naming, graph-store conventions, occasionally auth — so a backend is a small set
of store-specific pieces: how to read its config, upload the `given` data, and
run each query type. Multimethods let a backend register a handful of flat,
direct functions against the store-type / query-type axes, adding the whole slice
without editing shared code.

Two shapes were explicitly being avoided:

1. The same store-type switch copy-pasted across the config path, the upload path
   and the query path — three places to keep in step.
2. Layers of abstract classes whose only end product is a single HTTP request.
   A request is fundamentally a map — URL, method, params, headers, body — and
   burying that map under a class hierarchy is an exemplar of what Rich Hickey
   calls interfaces hiding maps: the ossified interface obscures the open data
   underneath and stops you handling it generically. Each registered method here
   is kept flat: it builds the request — the map — directly, in one readable
   function, and dispatch happens on values, not on a type lattice.

The axes that dispatch this way:

- **triple store type** (`triple_store["type"]`) — RdfLib, GraphDb, Anzo, Stardog
- **SPARQL query type** (`when.queryType`) — Select, Construct, Update, …
- **spec component source + predicate** (`data_source_type`, `given`/`when`/`then`)
- **result type** (`SpecResult` subclass)

Measured reuse, so the rationale rests on fact rather than folklore:

| multimethod | implementations | call sites |
|---|---|---|
| `get_spec_component` | 24 | 1 |
| `run_when_impl` | 13 | 1 (+ recursive) |
| `render_result_diff` | 9 | 2 |
| `get_triple_store_config` | 5 | 1 |
| `combine_specs` | 5 | 1 |
| `compare_table_results` | 4 | 1 |
| `upload_given` | 4 | 1 |

The dispatch decision is almost never *reused* across call sites — it is one call
site with many implementations. So the value is a cohesive, flat extension point
(and, where there are many cases, readability over a giant `if/elif`), not reuse.

## Decision
Add a backend / query type / source / result type by registering a method on the
relevant multimethod, and keep that method a flat, direct implementation rather
than a layer in an abstraction stack. A *runtime precondition* that is not a
dispatch key stays a guard, not a method — e.g. "is the configured store Anzo?"
inside a handler that already dispatched on the spec's declared source (see
`require_anzo`).

Detector for the abstraction stack this avoids — indirection vs abstraction:
delete the wrapper classes and imagine what's left is the data (a dict) plus the
single call that consumes it. If no capability is lost, the layers were
indirection dressed as abstraction: a real abstraction removes detail, indirection
only relocates it. Prefer the flat form.

## Tripwire: reconsider in the agentic-coding age
The usual argument for this pattern is that hand-written switches get copy-pasted
and the copies drift. That argument is weaker — and differently shaped — when an
agent is doing the editing:

- An agent applies a found fix quickly and consistently across the sites it has
  in hand. It does *not* have the human's "…I'm sure there's a third site" itch,
  so it can be **confidently incomplete** when a copy it never loaded exists. The
  scarce skill is finding every site and being sure; execution is cheap.
- Therefore the drift/hidden-site argument justifies the pattern only where an
  axis is genuinely switched in **more than one place** (here, essentially
  `render_result_diff`). At the single-call-site axes above, a local `if/elif`
  has no second copy to drift from and may read better.
- A multimethod that scatters `@method` registrations across modules can
  *recreate* the find-all-the-sites problem it was meant to remove.

Rule going forward: prefer whatever makes completeness a **structural fact at the
point of change** — one dispatch table where an axis is switched in many places;
one local block where it is switched in one. Do not reach for a multimethod
reflexively. Revisit this ADR if tooling shifts the economics again.

## Consequences
- **Advantages**:
  - A new backend is a cohesive slice of flat functions, no shared hierarchy.
  - Where an axis has many cases, one table reads better than a long `if/elif`.
  - Where an axis is switched in several places, the table removes the hidden-site
    problem — which matters more, not less, with an agent editing.
- **Trade-offs**:
  - Dispatch is by value/type at runtime, so a missing case surfaces at call time
    via `Default`, not at import.
  - Scattered registration can hide the set of cases; see the tripwire.
  - The `multimethods` library is less familiar than `if`/`match` (see ADR 0004).
- **Alternatives Considered**:
  - *`if`/`elif` copied across the config/upload/query paths*: the multi-site
    drift this avoids.
  - *A stack of abstract classes ending in one HTTP request*: rejected as
    interfaces hiding a map (Hickey) — the request is data and should stay data;
    flat per-backend functions that build it directly, dispatched on values.
  - *`match` / `functools.singledispatch` / a `{key: handler}` dict*: reasonable
    standard-library options, and preferable where a single local dispatch is all
    that is needed.

## Future Considerations
- `check_result`'s comparison/failure-type choice and the pass/fail
  classification of results are still hand-written conditionals. Leave them until
  touched; when touched, apply the tripwire rule rather than converting on
  principle.
- The multimethod definitions link back to this ADR so the rule — including the
  tripwire — is visible at the point of change.
