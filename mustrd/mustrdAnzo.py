from rdflib import Graph, ConjunctiveGraph, Literal, URIRef
from requests import ConnectTimeout, HTTPError, ConnectionError
import logging
from mustrd.anzo_utils import query_azg, query_graphmart
from mustrd.anzo_utils import query_configuration, json_to_dictlist, ttl_to_graph



def execute_select(triple_store: dict,  when: str, bindings: dict = None) -> str:
    try:
        if bindings:
            when = query_with_bindings(bindings, when)
        # FIXME: why do we have those tokens in a select query? in particular ${targetGraph}?
        # FIXME: why do we also query the output graph?
        when = when.replace("${fromSources}",
                            f"FROM <{triple_store['input_graph']}>\nFROM <{triple_store['output_graph']}>").replace(
                                "${targetGraph}", f"<{triple_store['output_graph']}>")
        # TODO: manage results here
        return query_azg(anzo_config=triple_store, query=when, data_layers=[triple_store['input_graph']])
    except (ConnectionError, TimeoutError, HTTPError, ConnectTimeout):
        raise


def execute_update(triple_store: dict, when: str, bindings: dict = None) -> Graph:
    logging.debug(f"updating in anzo! {triple_store=} {when=}")
    input_graph = triple_store['input_graph']
    output_graph = triple_store['output_graph']

    # FIXME: that will only work with steps.
    # We could replace USING clauses with using-graph-uri parameter
    # But there is no parameter for default insert graphs.
    substituted_query = when.replace("${usingSources}",
                                     f"""USING <{input_graph}>
USING <{triple_store['output_graph']}>""").replace(
                                         "${targetGraph}", f"<{output_graph}>")

    response = query_azg(anzo_config=triple_store, query=substituted_query, is_update=True,
                         data_layers=[input_graph, output_graph], format="ttl")
    logging.debug(f'response {response}')
    # TODO: deal with error responses
    new_graph = ttl_to_graph(query_azg(anzo_config=triple_store, query="construct {?s ?p ?o} { ?s ?p ?o }",
                                       format="ttl", data_layers=output_graph))
    logging.debug(f"new_graph={new_graph.serialize(format='ttl')}")
    return new_graph


def execute_construct(triple_store: dict, when: str, bindings: dict = None) -> Graph:
    try:
        if bindings:
            when = query_with_bindings(bindings, when)
        return ttl_to_graph(query_azg(anzo_config=triple_store, query=when, format="ttl",
                                      data_layers=triple_store['input_graph']))
    except (ConnectionError, TimeoutError, HTTPError, ConnectTimeout) as e:
        logging.error(f'response {e}')
        raise


def query_with_bindings(bindings: dict, when: str) -> str:
    values = ""
    for key, value in bindings.items():
        values += f"VALUES ?{key} {{{value.n3()}}} "
    split_query = when.lower().split("where {", 1)
    return f"{split_query[0].strip()} WHERE {{ {values} {split_query[1].strip()}"


# Get Given or then from the content of a graphmart
def get_spec_component_from_graphmart(triple_store: dict, graphmart: URIRef, layer: URIRef = None) -> ConjunctiveGraph:
    try:
        return ttl_to_graph(query_graphmart(anzo_config=triple_store, graphmart=graphmart,
                                            query="CONSTRUCT {?s ?p ?o} WHERE {?s ?p ?o}",
                                            data_layers=layer, format="ttl"))
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
    result = json_to_dictlist(query_configuration(
        anzo_config=triple_store, query=query))
    if len(result) == 0:
        raise FileNotFoundError(
            f"Query {query_name} not found in folder {folder_name}")
    return result[0].get("query")


# https://github.com/Semantic-partners/mustrd/issues/102
def get_query_from_step(triple_store: dict, query_step_uri: URIRef) -> str:
    query = f"""SELECT ?query WHERE {{
        BIND(<{query_step_uri}> as ?stepUri)
            ?stepUri a <http://cambridgesemantics.com/ontologies/Graphmarts#Step>;
                     <http://cambridgesemantics.com/ontologies/Graphmarts#transformQuery> ?query
    }}"""
    return json_to_dictlist(query_configuration(anzo_config=triple_store, query=query))[0]['query']


def get_queries_from_templated_step(triple_store: dict, query_step_uri: URIRef) -> dict:
    query = f"""SELECT ?param_query ?query_template WHERE {{
        BIND(<{query_step_uri}> as ?stepUri)
            ?stepUri    a <http://cambridgesemantics.com/ontologies/Graphmarts#Step> ;
                        <http://cambridgesemantics.com/ontologies/Graphmarts#parametersTemplate> ?param_query ;
                        <http://cambridgesemantics.com/ontologies/Graphmarts#template> ?query_template .
    }}
    """
    return json_to_dictlist(query_configuration(anzo_config=triple_store, query=query))[0]


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
    return json_to_dictlist(query_configuration(anzo_config=triple_store, query=query))


def upload_given(triple_store: dict, given: Graph):
    logging.debug(f"upload_given {triple_store} {given}")

    try:
        clear_graph(triple_store, triple_store['input_graph'])
        clear_graph(triple_store, triple_store['output_graph'])
        serialized_given = given.serialize(format="nt")
        insert_query = f"INSERT DATA {{graph <{triple_store['input_graph']}>{{{serialized_given}}}}}"
        query_azg(anzo_config=triple_store, query=insert_query, is_update=True)
    except (ConnectionError, TimeoutError, HTTPError, ConnectTimeout):
        logging.error("Exception occurred while uploading given graph", exc_info=True)
        raise


def clear_graph(triple_store: dict, graph_uri: str):
    try:
        clear_query = f"CLEAR GRAPH <{graph_uri}>"
        query_azg(anzo_config=triple_store, query=clear_query, is_update=True)
    except (ConnectionError, TimeoutError, HTTPError, ConnectTimeout):
        logging.error(f"Failed to clear graph {graph_uri} in triple store {triple_store['name']}")
        raise
