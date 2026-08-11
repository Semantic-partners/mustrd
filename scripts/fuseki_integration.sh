#!/usr/bin/env bash
#
# Run mustrd's spec suite against a real Apache Jena Fuseki.
#
# Why this exists. Every HTTP backend in mustrd — GraphDb, Anzo, Stardog — is
# mock-tested only, because each needs a licence or a server nobody has in CI. The
# request building, Accept headers, dataset parameters and `given`-upload round
# trip are shared shapes, so driving a real Fuseki covers the parts of those
# backends that are not vendor-specific. Writing this backend found four bugs that
# mocks could not: a per-graph upload leaking data between specs, bindings
# rewriting the SELECT projection, unqualified updates missing a named input
# graph, and a spec in our own suite relying on rdflib resolving an undeclared
# prefix.
#
# The suite it runs is the SAME expected-success specs the RdfLib run uses. That is
# the point: one set of specs, two engines.
#
# Usage:
#   scripts/fuseki_integration.sh            # start Fuseki, run, leave it up
#   KEEP=0 scripts/fuseki_integration.sh     # ... and stop it afterwards
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
compose="docker/fuseki-compose.yml"
base="http://localhost:3033"

echo "==> Starting Fuseki"
docker compose -f "$compose" up -d >/dev/null
if [ "${KEEP:-1}" = "0" ]; then
    trap 'docker compose -f "$compose" down >/dev/null 2>&1 || true' EXIT
fi

echo "==> Waiting for it to answer"
for _ in $(seq 1 60); do
    if curl -fsS "$base/ds/sparql" --data-urlencode 'query=ASK{}' \
        -H "Accept: application/sparql-results+json" >/dev/null 2>&1; then
        break
    fi
    sleep 2
done
curl -fsS "$base/ds/sparql" --data-urlencode 'query=ASK{}' \
    -H "Accept: application/sparql-results+json" >/dev/null

# This image protects writes even though queries are open, so mustrd needs the
# credentials — via the `_secrets` file beside the triplestore config, which is
# where mustrd looks and which .gitignore keeps out of the repo.
secrets="test/test-mustrd-config/fuseki_config_example_secrets.ttl"
if [ ! -f "$secrets" ]; then
    echo "==> Writing $secrets"
    cat > "$secrets" <<'SECRETS'
@prefix : <https://mustrd.org/triplestore/> .
:fuseki_local a :Fuseki ;
    :username "admin" ;
    :password "admin" .
SECRETS
fi

echo "==> Running the spec suite against Fuseki"
poetry run pytest --mustrd --config=test/test-mustrd-config/test_mustrd_fuseki.ttl \
    -q -p no:cacheprovider "$@" \
    || python -m pytest --mustrd --config=test/test-mustrd-config/test_mustrd_fuseki.ttl \
        -q -p no:cacheprovider "$@"

echo
echo "PASS: the spec suite runs against a real Fuseki."
