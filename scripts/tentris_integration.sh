#!/usr/bin/env bash
#
# Run mustrd's spec suite against a local Tentris.
#
# The counterpart to scripts/fuseki_integration.sh, and the reason the two exist:
# both drive the SAME expected-success specs, so the claim that a spec is portable
# is checked rather than asserted. Fuseki extends SPARQL where Tentris keeps to it,
# which is what makes the pair worth having — between them they catch a spec that
# only works because one engine was lenient.
#
# Unlike Fuseki this does NOT run in CI. Tentris is not a public image and needs a
# licence, so the binary has to be on the machine already. The script says so and
# stops rather than pretending.
#
# Usage:
#   scripts/tentris_integration.sh                 # start one, run, leave it up
#   TENTRIS_PORT=9081 scripts/tentris_integration.sh
#   KEEP=0 scripts/tentris_integration.sh          # ... and stop it afterwards
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
port="${TENTRIS_PORT:-9080}"
base="http://127.0.0.1:${port}"

if ! command -v tentris >/dev/null 2>&1; then
    echo "tentris is not on PATH. It is not a public image and needs a licence, so"
    echo "this suite only runs where the binary is already installed."
    echo "Fuseki covers the same specs in CI: scripts/fuseki_integration.sh"
    exit 1
fi

started=""
if curl -fsS "$base/sparql" --data-urlencode 'query=ASK{}' \
        -H "Accept: application/sparql-results+json" >/dev/null 2>&1; then
    echo "==> Using the Tentris already serving on $port"
else
    datastore="$(mktemp -d)"
    chmod 700 "$datastore"          # tentris refuses a datastore with looser permissions
    echo "==> Initialising a datastore in $datastore"
    tentris -s "$datastore" init >/dev/null 2>&1

    echo "==> Starting Tentris on $port"
    tentris -s "$datastore" serve "127.0.0.1:${port}" >"$datastore/serve.log" 2>&1 &
    started=$!
    if [ "${KEEP:-1}" = "0" ]; then
        trap 'kill "$started" 2>/dev/null || true; rm -rf "$datastore"' EXIT
    fi

    for _ in $(seq 1 60); do
        curl -fsS "$base/sparql" --data-urlencode 'query=ASK{}' \
            -H "Accept: application/sparql-results+json" >/dev/null 2>&1 && break
        sleep 1
    done
fi

curl -fsS "$base/sparql" --data-urlencode 'query=ASK{}' \
    -H "Accept: application/sparql-results+json" >/dev/null

echo "==> Running the spec suite against Tentris"
config=test/test-mustrd-config/test_mustrd_tentris.ttl
poetry run pytest --mustrd --config="$config" -q -p no:cacheprovider "$@" \
    || python -m pytest --mustrd --config="$config" -q -p no:cacheprovider "$@"

echo
echo "PASS: the spec suite runs against a real Tentris."
