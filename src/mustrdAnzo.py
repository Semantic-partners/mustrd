import requests
from pyanzo import AnzoClient
from rdflib import Graph
from requests import ConnectTimeout, Response, HTTPError
from bs4 import BeautifulSoup


# https://github.com/Semantic-partners/mustrd/issues/73
# add parameter types and return types
def manage_anzo_response(response: Response) -> str:
    content_string = response.content.decode("utf-8")
    if response.status_code == 200:
        return content_string
    elif response.status_code == 403:
        html = BeautifulSoup(content_string, 'html.parser')
        title_tag = html.title.string
        raise HTTPError(f"Anzo authentication error, status code: {response.status_code}, content: {title_tag}")
    else:
        raise Exception(f"Anzo error, status code: {response.status_code}, content: {content_string}")


def query_with_bindings(bindings: dict, when: str) -> str:
    values = ""
    for key, value in bindings.items():
        values += f"VALUES ?{key} {{{value.n3()}}} "
    split_query = when.lower().split("where {", 1)
    return f"{split_query[0].strip()} WHERE {{ {values} {split_query[1].strip()}"


def execute_select(triple_store: dict, given: Graph, when: str, bindings: dict = None) -> str:
    try:
        clear_graph(triple_store)
        upload_given(triple_store, given)
        if bindings:
            when = query_with_bindings(bindings, when)
        data = {'datasourceURI': triple_store['gqe_uri'], 'query': when,
                'default-graph-uri': triple_store['input_graph'], 'skipCache': 'true'}
        url = f"https://{triple_store['url']}:{triple_store['port']}/sparql?format=application/sparql-results+json"
        return manage_anzo_response(requests.post(url=url,
                                                  auth=(triple_store['username'], triple_store['password']),
                                                  data=data,
                                                  verify=False))
    except (ConnectionError, TimeoutError, HTTPError, ConnectTimeout):
        raise


def execute_construct(triple_store: dict, given: Graph, when: str, bindings: dict = None) -> Graph:
    try:
        clear_graph(triple_store)
        upload_given(triple_store, given)
        if bindings:
            when = query_with_bindings(bindings, when)
        data = {'datasourceURI': triple_store['gqe_uri'], 'query': when,
                'default-graph-uri': triple_store['input_graph'], 'skipCache': 'true'}
        url = f"https://{triple_store['url']}:{triple_store['port']}/sparql?format=ttl"
        return Graph().parse(data=manage_anzo_response(requests.post(url=url,
                                                                     auth=(triple_store['username'],
                                                                           triple_store['password']),
                                                                     data=data,
                                                                     verify=False)))
    except (ConnectionError, TimeoutError, HTTPError, ConnectTimeout):
        raise


# Get Given or then from the content of a graphmart
def get_spec_component_from_graphmart(triple_store: dict, graphmart, layer=None):
    anzo_client = AnzoClient(triple_store['url'], triple_store['port'], triple_store['username'],
                             triple_store['password'])
    return anzo_client.query_graphmart(graphmart=graphmart, data_layers=layer,
                                       query_string="CONSTRUCT {?s ?p ?o} WHERE {?s ?p ?o}",
                                       skip_cache=True).as_quad_store()


def get_query_from_querybuilder(triple_store: dict, folder_name, query_name):
    query = f"""SELECT ?query WHERE {{
        graph ?queryFolder {{
            ?bookmark a <http://www.cambridgesemantics.com/ontologies/QueryPlayground#QueryBookmark>;
                        <http://openanzo.org/ontologies/2008/07/System#query> ?query;
                        <http://purl.org/dc/elements/1.1/title> "{query_name}"
            }}
            ?queryFolder a <http://www.cambridgesemantics.com/ontologies/QueryPlayground#QueryFolder>;
                        <http://purl.org/dc/elements/1.1/title> "{folder_name}"
    }}"""
    anzo_client = AnzoClient(triple_store['url'], triple_store['port'], triple_store['username'],
                             triple_store['password'])
    return anzo_client.query_journal(query_string=query).as_table_results().as_record_dictionaries()[0].get(
        "query")


def get_query_from_step(triple_store: dict, query_step_uri):
    query = f"""SELECT ?query WHERE {{
        BIND(<{query_step_uri}> as ?stepUri)
        graph ?stepUri {{
            ?stepUri a <http://cambridgesemantics.com/ontologies/Graphmarts#Step>;
            <http://cambridgesemantics.com/ontologies/Graphmarts#transformQuery> ?query
        }}
    }}
    """
    anzo_client = AnzoClient(triple_store['url'], triple_store['port'], triple_store['username'],
                             triple_store['password'])
    return anzo_client.query_journal(query_string=query).as_table_results().as_record_dictionaries()[0].get(
        "query")


def upload_given(triple_store: dict, given: Graph):
    try:
        serialized_given = given.serialize(format="nt")
        insert_query = f"INSERT DATA {{graph <{triple_store['input_graph']}>{{{serialized_given}}}}}"
        data = {'datasourceURI': triple_store['gqe_uri'], 'update': insert_query}
        response = requests.post(url=f"https://{triple_store['url']}:{triple_store['port']}/sparql",
                                 auth=(triple_store['username'], triple_store['password']), data=data, verify=False)
        manage_anzo_response(response)
    except (ConnectionError, TimeoutError, HTTPError, ConnectTimeout):
        raise


def clear_graph(triple_store: dict):
    try:
        clear_query = f"CLEAR GRAPH <{triple_store['input_graph']}>"
        data = {'datasourceURI': triple_store['gqe_uri'], 'update': clear_query}
        response = requests.post(url=f"https://{triple_store['url']}:{triple_store['port']}/sparql",
                                 auth=(triple_store['username'], triple_store['password']), data=data, verify=False)
        manage_anzo_response(response)
    except (ConnectionError, TimeoutError, HTTPError, ConnectTimeout):
        raise

