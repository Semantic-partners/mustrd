# ADR 0005: Keep Credentials Out of the Config Graph

## Context
A triple store configuration is an RDF graph: URLs, ports, repository/database
names, input/output graphs, and so on. Credentials (usernames, passwords, bearer
tokens) are about the same store but are a different kind of data with a
different lifecycle: config is read, diffed, logged and committed freely;
credentials must not be.

The config graph is handled in many places for legitimate reasons — validation,
serialisation, logging, error reporting, coverage artifacts. If credentials live
in that graph, every one of those points can disclose them. Keeping secrets out
of the graph is therefore a property worth preserving even though it means config
and credentials are loaded separately.

## Decision
Credentials are not merged into the config graph. They are loaded separately into
a map keyed by store URI (`{store IRI: {token/username/password}}`) and applied
to each store's config at parse time through a single helper. The secrets source
is parsed into a throwaway graph purely to build the map, which is then discarded
— the secret triples never join the config graph.

- `get_triple_store_graph` loads config only.
- `get_credentials` builds the map (from the inline `--secrets` turtle, or the
  sibling `<config>_secrets<ext>` file), then discards the parsed graph.
- `get_triple_stores(graph, credentials)` takes the map; `apply_credentials`
  copies each store's auth onto its config dict.

The turtle `_secrets` file format and naming convention are unchanged, so
existing setups keep working. `get_triple_stores` also falls back to reading auth
embedded in the passed graph when no map is given, for direct callers.

## Consequences
- **Advantages**:
  - The config graph can be serialised, logged or dumped without exposing auth.
  - Credentials are one concern in one place, rather than read inline by each
    backend during config parsing.
  - Absent credentials stay absent (and are caught by the required-parameter
    check) instead of becoming the string `"None"`.
- **Trade-offs**:
  - Config and credentials are two artifacts to reason about rather than one
    graph. This separation is deliberate; see Context.
- **Alternatives Considered**:
  - *Merging secrets into the config graph*: rejected — it reintroduces the
    disclosure risk this ADR exists to prevent.
  - *Secrets in their own named graph within the config dataset*: a full
    serialisation still emits every named graph, so it does not prevent the leak.
  - *A separate secrets file format (`.env`/TOML)*: the format is orthogonal to
    the decision. Keeping secrets out of the graph is the point, and changing the
    turtle format would break existing users for no additional security benefit.

## Future Considerations
- The credentials map is the seam for any future secrets source (environment
  variables, a secret manager, a `.env`/TOML file): populate the map and nothing
  downstream changes.
- Before merging the secrets source into the config graph for convenience, read
  this ADR. `get_triple_store_graph` and `get_credentials` link back to it.
