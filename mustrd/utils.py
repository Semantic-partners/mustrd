import json
import warnings
from contextlib import contextmanager
from pathlib import Path

from requests import HTTPError, RequestException, Response


# Keep this function in a file directly under project root / src
def get_mustrd_root() -> Path:
    return Path(__file__).parent


def manage_http_response(response: Response, store_label: str, *,
                         success_codes=(200, 204),
                         auth_codes=(401,),
                         http_error_codes=(),
                         auth_detail=None) -> str:
    """Shared handling of a triple store's HTTP SPARQL response.

    The backends (GraphDB, Stardog, Anzo) differ only in which status codes mean
    success vs auth failure, and how the auth-error detail is extracted — so those
    are parameters. The exception *types* are deliberately the same across
    backends: run_spec classifies an HTTPError as a connection error and a
    RequestException as an execution error, so which one a status raises is
    behaviour, not cosmetics (e.g. GraphDB's 406 stays an HTTPError).

    - success_codes: return the body (204/no body -> None)
    - auth_codes: raise HTTPError, with auth_detail(content) if given else content
    - http_error_codes: raise HTTPError (non-auth, e.g. GraphDB 406)
    - anything else: raise RequestException
    """
    content = response.content.decode("utf-8")
    code = response.status_code
    if code in success_codes:
        return content or None
    if code in auth_codes:
        detail = auth_detail(content) if auth_detail else content
        raise HTTPError(f"{store_label} authentication error, status code: {code}, content: {detail}")
    if code in http_error_codes:
        raise HTTPError(f"{store_label} error, status code: {code}, content: {content}")
    raise RequestException(f"{store_label} error, status code: {code}, content: {content}")


def is_json(myjson: str) -> bool:
    try:
        json.loads(myjson)
    except ValueError:
        return False
    return True


@contextmanager
def rdflib_internals_quiet():
    """Suppress deprecations rdflib raises about its OWN internals.

    rdflib 7.6 deprecated `ConjunctiveGraph`, `Dataset.default_context` and
    `Dataset.identifier` while its own internals still reach them — the TriG
    parser builds a ConjunctiveGraph, `triples()` on a union dataset compares
    against `default_context`, `Graph.__repr__` reads `identifier`. Each of those
    warnings names the mustrd line that called in, so a user saw deprecations
    about code they could not reach and could not act on. In the wild that was
    fourteen per run.

    Scoped by CALLER, which is what makes it safe rather than a blanket mute:
    rdflib raises these with `stacklevel=2`, so each is attributed to whoever
    called in, and a `module="rdflib.*"` filter therefore silences
    rdflib-calling-rdflib and nothing else. mustrd reaching for a deprecated API
    directly is still reported, even inside here.
    test_no_deprecation_warnings.py holds both halves of that line.
    """
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore", category=DeprecationWarning, module=r"rdflib\..*")
        yield
