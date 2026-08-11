#!/usr/bin/env bash
#
# Run mustrd the way a user does: installed from a built wheel, from a directory
# that is not this repo.
#
# Why this exists. CI's plugin step installs with `pip install -e .`, which keeps
# the source tree on the path — so package-data problems, path resolution that
# accidentally depends on the checkout, and anything that only appears from
# site-packages were never exercised. 0.8.0rc1 shipped fourteen deprecation
# warnings per run and the way we found out was a user installing it.
#
# Two properties do the work here, and both are easy to lose:
#   1. A REAL wheel install, not editable.
#   2. Run from a temp directory OUTSIDE the repo, so nothing can resolve back
#      into the source tree and quietly work.
#
# Warnings from mustrd's own code are errors, matching pytest.ini — but pytest.ini
# does not apply here (we are not in the repo), so they are passed explicitly.
#
# Usage: scripts/consumer_smoke.sh
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

echo "==> Building a wheel"
rm -rf "$repo_root/dist-smoke"
poetry build -f wheel -o "$repo_root/dist-smoke"
wheel="$(ls "$repo_root"/dist-smoke/*.whl | head -1)"
echo "    $(basename "$wheel")"

echo "==> Installing it into a clean venv (not editable, no repo on the path)"
python -m venv "$work/venv"
if [ -d "$work/venv/bin" ]; then venv_bin="$work/venv/bin"; else venv_bin="$work/venv/Scripts"; fi
"$venv_bin/python" -m pip install --quiet --upgrade pip
"$venv_bin/python" -m pip install --quiet "$wheel" pytest

echo "==> Copying the fixture out of the repo"
cp -r "$repo_root/test/consumer-smoke" "$work/project"
cd "$work/project"

echo "==> Checking it is the INSTALLED mustrd, carrying its own model files"
# Run from the fixture dir, never the repo: python prepends the working directory
# to sys.path, so `import mustrd` next to the source tree imports the source tree
# and this whole script silently tests nothing. The assertion below is what stops
# that regressing — the first version of this script had exactly that bug.
#
# The model files matter because mustrd loads its ontology and SHACL shapes from
# package data at runtime. Missing from the wheel, every spec fails for a consumer
# and passes for us.
MUSTRD_VENV="$work/venv" "$venv_bin/python" - <<'PY'
import os
from pathlib import Path

import mustrd

root = Path(mustrd.__file__).resolve().parent
venv = Path(os.environ["MUSTRD_VENV"]).resolve()
assert venv in root.parents, (
    f"imported mustrd from {root}, not from the venv at {venv} — this script is "
    "testing the source tree, not the wheel")

missing = [name for name in ("model/mustrdShapes.ttl", "model/ontology.ttl")
           if not (root / name).is_file()]
assert not missing, f"wheel is missing package data: {missing}"
print(f"    ok: {root}")
PY

echo "==> Running specs against the installed mustrd, from $work/project"
# The fixture carries its own pytest.ini making mustrd's deprecations failures.
# Not passed as -W here: pytest escapes the module field of a command-line -W
# literally, so `-W error::DeprecationWarning:mustrd.*` matches nothing at all.
# In an ini it is a regex and bites. Both verified against the 0.8.0rc1 tag.
"$venv_bin/python" -m pytest --mustrd --config=mustrd-config.ttl -q \
    -p no:cacheprovider

echo "==> Smoking the CLI"
"$venv_bin/python" -m mustrd --help >/dev/null
"$venv_bin/python" -m mustrd report --config mustrd-config.ttl --md "$work/report.md" >/dev/null
test -s "$work/report.md" || { echo "CLI produced no report"; exit 1; }
echo "    ok: $(wc -l < "$work/report.md") lines of report"

rm -rf "$repo_root/dist-smoke"
echo
echo "PASS: mustrd works when installed."
