# Contributing to mustrd

Issues and pull requests are welcome. This file is the things that are not obvious
from reading the code.

For how a release is cut, see [RELEASING.md](RELEASING.md) — that is a maintainer
task and deliberately separate from this file.

## Setup

```bash
poetry install
poetry run pip install -e .    # so the pytest plugin resolves to your working copy
```

`pyproject.toml` and `poetry.lock` are the only sources of dependency truth. There is
no exported `requirements.txt` to keep in step.

## There are two test suites, and they are different

CI runs both. Running one and seeing green is the easiest mistake to make here.

```bash
# 1. unit tests — plain pytest over test/
poetry run pytest test/ --doctest-modules --config=pytest.ini

# 2. mustrd against its own specs, through the plugin
poetry run pytest --mustrd --config=test/test_config_local.ttl
```

The second is mustrd testing itself: the `.mustrd.ttl` files under
`test/test-specs/expected-success/` are run as specs. A change to spec parsing or
execution shows up there and nowhere else.

At the time of writing that is 191 and 230 passing respectively.

The viewer's browser tests need a real browser, and skip themselves rather than fail
if it is absent — so they can look green when they never ran:

```bash
poetry run playwright install chromium
poetry run pytest test/test_viewer_browser.py
```

CI runs those once, on Linux/3.11 only. The full matrix is Linux and Windows across
Python 3.11, 3.12 and 3.13.

Lint is `flake8` via `lint.yml`, with `--exit-zero` — advisory, it cannot fail the
build. Don't take a clean CI run as evidence the file is clean.

## Adding a spec to `expected-success` means editing three lists

`test/test_pytest_mustrd.py` asserts the collected spec names against three
hardcoded enumerations (`test_collection_path` and the two `startsWithCheck` tests).
Add a `.mustrd.ttl` under `test/test-specs/expected-success/` and all three fail
until you add the filename to each. They are sorted, except the first, which is a set.

This is unpleasant and known. Conform to it rather than fixing it in the same PR as
something else.

A file that declares no `must:TestSpec` — a competency-question index, say — adds no
specs and needs no list edits.

## Dependencies: no exact pins

Don't pin an exact version in `[tool.poetry.dependencies]`. It forces that version on
everyone who installs mustrd, and it makes every future CVE in that package something
only we can clear. Use a caret or an explicit range.

**When a new release of a dependency breaks us, fix the code.** Do not pin backwards
to make the failure go away — that is how the two worst dependency problems in this
repo happened, and both are worked examples:

- `urllib3` was pinned to `1.26.19` because mustrd mutated `DEFAULT_CIPHERS`, which
  urllib3 2.0 removed. The pin held the package five advisories behind. See the note
  in `mustrd/anzo_utils.py`.
- rdflib was locked at `7.1.4` while `pyproject.toml` advertised `^7.1.3`. Every
  update spec failed on anything newer, because mustrd put its given data in a named
  graph and an unqualified `DELETE ... WHERE` operates on the default graph. rdflib
  had stopped being wrong; mustrd was relying on the bug.

If you touch a constraint, test both ends of the range. `pytest` is `>=7.2.0,<10` and
was verified on 7.4.4 and 9.1.1.

## Known rough edges

Worth knowing before you trip over them:

- `test/test_config_local_expected_failures.ttl` defines an expected-failures
  collection and **nothing references it** — no CI step, no test module. The
  `invalid_*.mustrd.ttl` specs are only reached by the collection-name tests, which
  check names and not outcomes. Nothing currently asserts that an invalid spec fails.
- `mustrd/README.md` and `mustrd/README.adoc` duplicate each other and are stale in
  places (they still reference a `src/run.py` that no longer exists).

## Writing RDF

Get [Mentor](https://github.com/faubulous/mentor-vscode) (`faubulous.mentor`) if you
use VS Code. A spec is just Turtle, so you get validation, go-to-definition from a
`must:fileurl` to the query it points at, and prefix renaming across the workspace.
