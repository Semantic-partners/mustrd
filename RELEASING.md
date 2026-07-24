# Releasing mustrd

Releases are cut by **pushing a version tag onto a commit**. The tag is the
single source of truth: it selects the exact SHA that ships and the version it
ships under. CI ([`.github/workflows/publish.yml`](.github/workflows/publish.yml))
builds that commit, publishes to PyPI, and cuts a matching GitHub Release with
auto-generated notes.

The committed `version` in `pyproject.toml` is cosmetic — the workflow overwrites
it at build time. You never edit it by hand to release.

## Version numbers are ordinals, not promises

We don't do semver. A version digit can't honestly encode "is this a breaking
change" — that's a human judgement, not something a `.` in a string decides
(Rich Hickey makes the case in [Spec-ulation](https://www.youtube.com/watch?v=oyLBGkS5ICk)).

So the number is just **the next number**. Pick whatever comes next on the
`0.x` line — `0.7.5`, `0.7.6`, `0.8.0` — based on how big the change *feels*, not
on a rule. It carries no compatibility guarantee. The only hard constraints:

- it must be a valid [PEP 440](https://peps.python.org/pep-0440/) version (so PyPI
  and pip order it correctly), and
- it must be higher than the last one (tags are monotonic; PyPI won't let you
  overwrite a version).

## Cut a release

```bash
# Final release — tag the SHA you want, no "v" prefix (tag == PyPI version)
git tag 0.7.5 <sha>        # omit <sha> to tag HEAD
git push origin 0.7.5
```

CI publishes `mustrd 0.7.5` to PyPI and creates GitHub Release `0.7.5`.

## Cut a candidate / beta

Append a PEP 440 pre-release suffix — `rc` (candidate), `b` (beta), or `a`
(alpha):

```bash
git tag 0.8.0rc1 <sha>
git push origin 0.8.0rc1
```

pip **hides pre-releases from normal installs**. `pip install mustrd` keeps
resolving the latest *final* version; a pre-release only lands if the user opts
in:

```bash
pip install --pre mustrd          # newest, including pre-releases
pip install mustrd==0.8.0rc1      # or pin the exact candidate
```

The GitHub Release is marked "pre-release" automatically when the version has an
`a`/`b`/`rc` suffix.

## Rehearsing a release

Pushing a **candidate tag** (`0.7.5rc1`) is a safe rehearsal: it's a real,
end-to-end publish to real PyPI, but pip won't serve it to normal installs, so
nobody gets it by accident. If it's wrong, bump the `rcN` and push again.

> A fully isolated sandbox — [TestPyPI](https://test.pypi.org), a separate
> throwaway PyPI instance with its own account/token — is possible but not wired
> up here (see the comment at the top of `publish.yml`). Candidate tags cover the
> same need without the extra account.

## If something goes wrong

- **Typo'd tag / bad version:** the workflow validates PEP 440 up front and fails
  before publishing. Delete the bad tag (`git push --delete origin <tag>`) and
  push a corrected one.
- **Bad release already on PyPI:** you can't overwrite a version. `yank` it on
  PyPI (hides it from resolution without breaking existing pins) and push the
  next ordinal with the fix.

## Auth

Publishing uses the `PYPI_API_TOKEN` repo secret (Poetry reads it as
`POETRY_PYPI_TOKEN_PYPI`). To rotate: regenerate the token on PyPI and update the
secret under repo **Settings → Secrets and variables → Actions**.
