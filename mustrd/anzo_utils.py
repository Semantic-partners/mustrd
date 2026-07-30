import json
import os
import ssl
from typing import List
from urllib.parse import quote
from rdflib import Graph
import requests
from requests import Response, HTTPError, RequestException
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)     # not the root logger: this is a library

# Talking to an Anzo with an old TLS stack.
#
# mustrd used to do this globally, by appending ":HIGH:!DH:!aNULL" to
# urllib3's DEFAULT_CIPHERS at import time — which is why urllib3 was pinned to
# 1.26.19. urllib3 2.0 deleted DEFAULT_CIPHERS, and its own defaults are stricter,
# so an Anzo that only offers legacy suites can now fail the handshake where it
# previously connected.
#
# The old behaviour is not restored by default: silently relaxing TLS for every
# user to suit one server is the wrong trade. Instead it is opt-in, and you choose
# the cipher string. For a genuinely old Anzo, lowering OpenSSL's security level is
# usually what is needed rather than naming suites:
#
#     export MUSTRD_SSL_CIPHERS='DEFAULT:@SECLEVEL=1'
#
# This applies only to Anzo requests. Those already pass verify=False, so the
# context below matches that rather than weakening anything further.
SSL_CIPHERS_ENV = "MUSTRD_SSL_CIPHERS"

_session = None


class _CipherAdapter(HTTPAdapter):
    """An adapter whose TLS context uses a caller-supplied OpenSSL cipher string."""

    def __init__(self, ciphers: str, **kwargs):
        self._ciphers = ciphers
        super().__init__(**kwargs)

    def init_poolmanager(self, *args, **kwargs):
        context = ssl.create_default_context()
        # Match the verify=False these requests already use, so this changes cipher
        # negotiation and nothing else.
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        context.set_ciphers(self._ciphers)
        kwargs["ssl_context"] = context
        return super().init_poolmanager(*args, **kwargs)


def anzo_session() -> requests.Session:
    """The session Anzo requests go through, cached.

    Plain unless MUSTRD_SSL_CIPHERS is set, in which case HTTPS gets a TLS context
    using that cipher string.
    """
    global _session
    if _session is None:
        _session = requests.Session()
        ciphers = os.environ.get(SSL_CIPHERS_ENV)
        if ciphers:
            logger.debug(f"Mounting Anzo TLS adapter with ciphers: {ciphers}")
            _session.mount("https://", _CipherAdapter(ciphers))
    return _session


def query_azg(anzo_config: dict, query: str,
              format: str = "json", is_update: bool = False,
              data_layers: List[str] = None):
    params = {
        'skipCache': 'true',
        'format': format,
        'datasourceURI': anzo_config['gqe_uri'],
        'using-graph-uri' if is_update else 'default-graph-uri': data_layers,
        'using-named-graph-uri' if is_update else 'named-graph-uri': data_layers
    }
    url = f"{anzo_config['url']}/sparql"
    return send_anzo_query(anzo_config, url=url, params=params, query=query, is_update=is_update)


def query_graphmart(anzo_config: dict,
                    graphmart: str,
                    query: str,
                    format: str = "json",
                    data_layers: List[str] = None):
    params = {
        'skipCache': 'true',
        'format': format,
        'default-graph-uri': data_layers,
        'named-graph-uri': data_layers
    }

    url = f"{anzo_config['url']}/sparql/graphmart/{quote(graphmart, safe='')}"
    return send_anzo_query(anzo_config, url=url, params=params, query=query)


def query_configuration(anzo_config: dict, query: str, format: str = "json"):
    params = {
        'format': format,
        'includeMetadataGraphs': True
    }
    url = f"{anzo_config['url']}/sparql"
    return send_anzo_query(anzo_config, url=url, params=params, query=query)


# https://github.com/Semantic-partners/mustrd/issues/73
def manage_anzo_response(response: Response) -> str:
    content_string = response.content.decode("utf-8")
    if response.status_code == 200:
        logging.debug(f"Response content: {content_string}")
        return content_string
    elif response.status_code == 403:
        html = BeautifulSoup(content_string, 'html.parser')
        title_tag = html.title.string
        raise HTTPError(f"Anzo authentication error, status code: {response.status_code}, content: {title_tag}")
    else:
        raise RequestException(f"Anzo error, status code: {response.status_code}, content: {content_string}")


def send_anzo_query(anzo_config, url, params, query, is_update=False):
    headers = {"Content-Type": f"application/sparql-{'update' if is_update else 'query' }"}
    logger.debug(f"send_anzo_query {url=} {query=} {is_update=}")
    return manage_anzo_response(anzo_session().post(url=url, params=params, data=query.encode('utf-8'),
                                                    auth=(anzo_config['username'], anzo_config['password']),
                                                    headers=headers, verify=False))


def json_to_dictlist(json_string: str):
    return list(map(lambda result: process_result(result), json.loads(json_string)['results']['bindings']))


def ttl_to_graph(ttl_string: str):
    return Graph().parse(data=ttl_string)


# Convert result to the right type
def process_result(result):
    xsd = "http://www.w3.org/2001/XMLSchema#"
    types = {
        f"{xsd}int": int,
        f"{xsd}integer": int,
        f"{xsd}decimal": float,
        f"{xsd}float": float,
        f"{xsd}double": float,
        f"{xsd}long": int
    }
    res = {}
    for key, type_value in result.items():
        if type_value['type'] in types:
            value = types[type_value['type']](type_value['value'])
        else:
            value = type_value['value']
        res.update({key: value})
    return res
