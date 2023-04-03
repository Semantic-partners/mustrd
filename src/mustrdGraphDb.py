import urllib.parse

import requests
from pyparsing import ParseException
from rdflib import Graph
from requests import ConnectionError, HTTPError


# https://github.com/Semantic-partners/mustrd/issues/72
def manage_graphdb_response(response) -> str:
    content_string = response.content.decode("utf-8")
    if response.status_code == 200:
        return content_string
    elif response.status_code == 204:
        pass
    elif response.status_code == 401:
        raise HTTPError(f"GraphDB authentication error, status code: {response.status_code}, content: {content_string}")
    else:
        raise Exception(f"GraphDb error, status code: {response.status_code}, content: {content_string}")


# wrap the entire select in another select to add the graph, allows for a more complicated where
def insert_graph(when, input_graph):
    new_when = f"SELECT * WHERE {{ GRAPH <{input_graph}> {{ {when} }} }}"
    return new_when


def parse_bindings(bindings: dict):
    bindings_string = ""
    for key, value in bindings.items():
        encoded_value = urllib.parse.quote_plus(f'{value.n3()}')
        bindings_string += f'&${key}={encoded_value}'
    return bindings_string


def execute_select(triple_store: dict, given: Graph, when: str, bindings: dict = None) -> str:
    # if "where {" not in when.lower():
    #     raise ParseException(pstr='GraphDB Implementation: No WHERE clause in query.')
    try:
        if triple_store["input_graph"] is None:
            drop_default_graph(triple_store)
        else:
            clear_graph(triple_store)
            when = insert_graph(when, triple_store["input_graph"])
        upload_given(triple_store, given)
        bindings_string = ""
        if bindings:
            bindings_string = parse_bindings(bindings)
        url = f"{triple_store['url']}:{triple_store['port']}/repositories/{triple_store['repository']}?query={when}{bindings_string}"
        headers = {
            'Accept': 'application/sparql-results+json'
        }
        return manage_graphdb_response(requests.request("GET",
                                                        url=url,
                                                        auth=(triple_store['username'], triple_store['password']),
                                                        headers=headers))
    except ConnectionError:
        raise


def execute_construct(triple_store: dict, given: Graph, when: str, bindings: dict = None) -> Graph:
    if "where {" not in when.lower():
        raise ParseException(pstr='GraphDB Implementation: No WHERE clause in query.')
    try:
        if triple_store["input_graph"] is None:
            drop_default_graph(triple_store)
        else:
            clear_graph(triple_store)
            split_when = when.lower().split("where {", 1)
            when = split_when[0] + "where { GRAPH <" + triple_store["input_graph"] + "> {" + split_when[1] + "}"
        upload_given(triple_store, given)
        bindings_string = ""
        if bindings:
            bindings_string = parse_bindings(bindings)
        url = f"{triple_store['url']}:{triple_store['port']}/repositories/{triple_store['repository']}?query={when}{bindings_string}"
        # return Graph().parse(data=manage_graphdb_response(requests.get(url=url)))
        return Graph().parse(data=manage_graphdb_response(requests.request("GET",
                                                                           url=url,
                                                                           auth=(triple_store['username'],
                                                                                 triple_store['password']))))

    except ConnectionError:
        raise


# https://github.com/Semantic-partners/mustrd/issues/22
def upload_given(triple_store: dict, given: Graph):
    try:
        serialized_given = given.serialize(format="nt")
        if triple_store["input_graph"] is None:
            insert_query = f"INSERT DATA {{ {serialized_given} }}"
        else:
            insert_query = urllib.parse.quote_plus(f"INSERT DATA {{graph <{triple_store['input_graph']}>"
                                                   f"{{{serialized_given}}}}}")
        response = requests.post(
            url=f"{triple_store['url']}:{triple_store['port']}/repositories/{triple_store['repository']}/statements?update={insert_query}",
            auth=(triple_store["username"], triple_store["password"]))
        manage_graphdb_response(response)
    except ConnectionError:
        raise


def clear_graph(triple_store: dict):
    try:
        clear_query = f"CLEAR GRAPH <{triple_store['input_graph']}>"
        response = requests.post(
            url=f"{triple_store['url']}:{triple_store['port']}/repositories/{triple_store['repository']}/statements?update={clear_query}",
            auth=(triple_store["username"], triple_store["password"]))
        manage_graphdb_response(response)
    except ConnectionError:
        raise


def drop_default_graph(triple_store: dict):
    try:
        clear_query = "DROP DEFAULT"
        response = requests.post(
            url=f"{triple_store['url']}:{triple_store['port']}/repositories/{triple_store['repository']}/statements?update={clear_query}",
            auth=(triple_store["username"], triple_store["password"]))
        manage_graphdb_response(response)
    except ConnectionError:
        raise
