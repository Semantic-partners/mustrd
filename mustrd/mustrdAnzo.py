"""
MIT License

Copyright (c) 2023 Semantic Partners Ltd

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import requests
from pyanzo import AnzoClient
from rdflib import Graph, ConjunctiveGraph, Literal, URIRef
from requests import ConnectTimeout, Response, HTTPError, RequestException, ConnectionError
from bs4 import BeautifulSoup
import logging
from .namespace import MUST


# https://github.com/Semantic-partners/mustrd/issues/73
def manage_anzo_response(response: Response) -> str:
    content_string = response.content.decode("utf-8")
    if response.status_code == 200:
        return content_string
    elif response.status_code == 403:
        html = BeautifulSoup(content_string, 'html.parser')
        title_tag = html.title.string
        raise HTTPError(f"Anzo authentication error, status code: {response.status_code}, content: {title_tag}")
    else:
        raise RequestException(f"Anzo error, status code: {response.status_code}, content: {content_string}")


def query_with_bindings(bindings: dict, when: str) -> str:
    values = ""
    for key, value in bindings.items():
        values += f"VALUES ?{key} {{{value.n3()}}} "
    split_query = when.lower().split("where {", 1)
    return f"{split_query[0].strip()} WHERE {{ {values} {split_query[1].strip()}"


def execute_select(triple_store: dict,  when: str, bindings: dict = None) -> str:
    try:
        if bindings:
            when = query_with_bindings(bindings, when)
        when = when.replace("${fromSources}", f"FROM <{triple_store['input_graph']}>\nFROM <{triple_store['output_graph']}>").replace(
        "${targetGraph}", f"<{triple_store['output_graph']}>")
        data = {'datasourceURI': triple_store['gqe_uri'], 'query': when,
                'default-graph-uri': triple_store['input_graph'],
                'named-graph-uri': triple_store['input_graph'],
                 'skipCache': 'true'}
        url = f"https://{triple_store['url']}:{triple_store['port']}/sparql?format=application/sparql-results+json"
        return manage_anzo_response(requests.post(url=url,
                                                  auth=(triple_store['username'], triple_store['password']),
                                                  data=data,
                                                  verify=False))
    except (ConnectionError, TimeoutError, HTTPError, ConnectTimeout):
        raise


def execute_update(triple_store: dict, when: str, bindings: dict = None) -> Graph:
    logging.debug(f"updating in anzo! {triple_store=} {when=}")
    input_graph = triple_store['input_graph']
    output_graph = triple_store['output_graph']

    substituted_query = when.replace("${usingSources}", f"USING <{triple_store['input_graph']}> \nUSING <{triple_store['output_graph']}>").replace(
        "${targetGraph}", f"<{output_graph}>")
   
    data = {'datasourceURI': triple_store['gqe_uri'],
            'update': substituted_query,
            'using-graph-uri': [output_graph, input_graph],
            'using-named-graph-uri': [output_graph, input_graph],
            'skipCache': 'true'}
    url = f"https://{triple_store['url']}:{triple_store['port']}/sparql?format=ttl"
    response = manage_anzo_response(requests.post(url=url,
            auth=(triple_store['username'],
                triple_store['password']),
            data=data,
            verify=False))
    logging.debug(f'response {response}')
    check_data = {'datasourceURI': triple_store['gqe_uri'], 'query': "construct {?s ?p ?o} { ?s ?p ?o }",
                'default-graph-uri': output_graph,
                'named-graph-uri': output_graph,
                  'skipCache': 'true'}
    everything_response = manage_anzo_response(requests.post(url=url,
            auth=(triple_store['username'],
                triple_store['password']),
            data=check_data,
            verify=False))
    # todo deal with error responses
    new_graph = Graph().parse(data=everything_response)
    logging.debug(f"new_graph={new_graph.serialize(format='ttl')}")
    return new_graph


def execute_construct(triple_store: dict, when: str, bindings: dict = None) -> Graph:
    try:
        if bindings:
            when = query_with_bindings(bindings, when)
        data = {'datasourceURI': triple_store['gqe_uri'], 'query': when,
                'default-graph-uri': triple_store['input_graph'],
                'named-graph-uri': triple_store['input_graph'],
                'skipCache': 'true'}
        url = f"https://{triple_store['url']}:{triple_store['port']}/sparql?format=ttl"
        response = requests.post(url=url,
            auth=(triple_store['username'],
                triple_store['password']),
            data=data,
            verify=False)
        logging.debug(f'response {response}')
        g = Graph().parse(data=manage_anzo_response(response))
        logging.debug(f"Actual Result = {g.serialize(format='ttl')}")
        return g
    except (ConnectionError, TimeoutError, HTTPError, ConnectTimeout) as e:
        logging.error(f'response {e}')
        raise


# Get Given or then from the content of a graphmart
def get_spec_component_from_graphmart(triple_store: dict, graphmart: URIRef, layer: URIRef = None) -> ConjunctiveGraph:
    try:
        anzo_client = AnzoClient(triple_store['url'], triple_store['port'],
                                 username=triple_store['username'],
                                 password=triple_store['password'])
        return anzo_client.query_graphmart(graphmart=graphmart,
                                           data_layers=layer,
                                           query_string="CONSTRUCT {?s ?p ?o} WHERE {?s ?p ?o}",
                                           skip_cache=True).as_quad_store().as_rdflib_graph()
    except RuntimeError as e:
        raise ConnectionError(f"Anzo connection error, {e}")


def get_query_from_querybuilder(triple_store: dict, folder_name: Literal, query_name: Literal) -> str:
    query = f"""SELECT ?query WHERE {{
        graph ?queryFolder {{
            ?bookmark a <http://www.cambridgesemantics.com/ontologies/QueryPlayground#QueryBookmark>;
                        <http://openanzo.org/ontologies/2008/07/System#query> ?query;
                        <http://purl.org/dc/elements/1.1/title> "{query_name}"
            }}
            ?queryFolder a <http://www.cambridgesemantics.com/ontologies/QueryPlayground#QueryFolder>;
                        <http://purl.org/dc/elements/1.1/title> "{folder_name}"
    }}"""
    anzo_client = AnzoClient(triple_store['url'], triple_store['port'],
                             username=triple_store['username'],
                             password=triple_store['password'])

    result = anzo_client.query_journal(query_string=query).as_table_results().as_record_dictionaries()
    if len(result) == 0:
        raise FileNotFoundError(f"Query {query_name} not found in folder {folder_name}")
    return result[0].get("query")


# https://github.com/Semantic-partners/mustrd/issues/102
def get_query_from_step(triple_store: dict, query_step_uri: URIRef) -> str:
    query = f"""SELECT ?stepUri ?query WHERE {{
        BIND(<{query_step_uri}> as ?stepUri)
            ?stepUri a <http://cambridgesemantics.com/ontologies/Graphmarts#Step>;
                     <http://cambridgesemantics.com/ontologies/Graphmarts#transformQuery> ?query
    }}
    # """
    anzo_client = AnzoClient(triple_store['url'], triple_store['port'],
                             username=triple_store['username'],
                             password=triple_store['password'])
    record_dictionaries = anzo_client.query_journal(query_string=query).as_table_results().as_record_dictionaries()

    return record_dictionaries[0].get(
        "query")

def get_queries_from_templated_step(triple_store: dict, query_step_uri: URIRef) -> dict:

    query = f"""SELECT ?stepUri ?param_query ?query_template WHERE {{
        BIND(<{query_step_uri}> as ?stepUri)
            ?stepUri    a <http://cambridgesemantics.com/ontologies/Graphmarts#Step> ;
   					    <http://cambridgesemantics.com/ontologies/Graphmarts#parametersTemplate> ?param_query ;
					    <http://cambridgesemantics.com/ontologies/Graphmarts#template> ?query_template .
    }}
    """
    anzo_client = AnzoClient(triple_store['url'], triple_store['port'],
                             username=triple_store['username'],
                             password=triple_store['password'])
    record_dictionaries = anzo_client.query_journal(query_string=query).as_table_results().as_record_dictionaries()
    return record_dictionaries[0]


def get_queries_for_layer(triple_store: dict, graphmart_layer_uri: URIRef):
    query = f"""PREFIX graphmarts: <http://cambridgesemantics.com/ontologies/Graphmarts#>
    PREFIX anzo: <http://openanzo.org/ontologies/2008/07/Anzo#>
SELECT ?query ?param_query ?query_template
  {{ <{graphmart_layer_uri}> graphmarts:step ?step .
  ?step         anzo:index ?index ;
                anzo:orderedValue ?query_step .
  ?query_step graphmarts:enabled true ;
  OPTIONAL {{  ?query_step
   				graphmarts:parametersTemplate ?param_query ;
           		graphmarts:template ?query_template ;
      . }}
  OPTIONAL {{  ?query_step
   				graphmarts:transformQuery ?query ;
      . }}
  }}
  ORDER BY ?index"""
    anzo_client = AnzoClient(triple_store['url'], triple_store['port'],
                             username=triple_store['username'],
                             password=triple_store['password'])
    return anzo_client.query_journal(query_string=query).as_table_results().as_record_dictionaries()


def upload_given(triple_store: dict, given: Graph):
    logging.debug(f"upload_given {triple_store} {given}")

    try:
        input_graph = triple_store['input_graph']
        output_graph = triple_store['output_graph']
        clear_graph(triple_store, input_graph)
        clear_graph(triple_store, output_graph)
        serialized_given = given.serialize(format="nt")
        insert_query = f"INSERT DATA {{graph <{triple_store['input_graph']}>{{{serialized_given}}}}}"
        data = {'datasourceURI': triple_store['gqe_uri'],
                'update': insert_query,
                'using-graph-uri': input_graph,
                'using-named-graph-uri': input_graph}
        response = requests.post(url=f"https://{triple_store['url']}:{triple_store['port']}/sparql",
                                    auth=(triple_store['username'], triple_store['password']), data=data, verify=False)
        manage_anzo_response(response)
    except (ConnectionError, TimeoutError, HTTPError, ConnectTimeout):
        raise


def clear_graph(triple_store: dict, graph_uri: str):
    try:
        clear_query = f"CLEAR GRAPH <{graph_uri}>"
        data = {'datasourceURI': triple_store['gqe_uri'], 'update': clear_query}
        url = f"https://{triple_store['url']}:{triple_store['port']}/sparql"
        response = requests.post(url=url,
                                 auth=(triple_store['username'], triple_store['password']), data=data, verify=False)
        manage_anzo_response(response)
    except (ConnectionError, TimeoutError, HTTPError, ConnectTimeout):
        raise
