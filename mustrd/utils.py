import json
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
