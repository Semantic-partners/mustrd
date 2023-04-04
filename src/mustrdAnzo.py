import requests
from pyanzo import AnzoClient
from rdflib import Graph
from requests import ConnectTimeout, Response


# https://github.com/Semantic-partners/mustrd/issues/73
# add parameter types and return types
def manage_anzo_response(response: Response) -> str:
    content_string = response.content.decode("utf-8")
    if response.status_code == 200:
        return content_string
    else:
        raise Exception(f"Anzo error, status code: {response.status_code}, content: {content_string}")


def query_with_bindings(bindings: dict, when: str) -> str:
    values = ""
    for key, value in bindings.items():
        values += f"VALUES ?{key} {{{value.n3()}}} "
    split_query = when.lower().split("where {", 1)
    return f"{split_query[0].strip()} WHERE {{ {values} {split_query[1].strip()}"

# https://github.com/Semantic-partners/mustrd/issues/14
class MustrdAnzo:
    def __init__(self, anzo_url, anzo_port, gqe_uri, input_graph, username=None, password=None):
        self.url = anzo_url
        self.port = anzo_port
        self.username = username
        self.password = password
        self.gqe_uri = gqe_uri
        self.input_graph = input_graph
        self.anzo_client = AnzoClient(self.url, self.port, self.username, self.password)

    def execute_select(self, given: Graph, when: str, bindings: dict = None) -> str:
        try:
            self.clear_graph()
            self.upload_given(given)
            if bindings:
                when = query_with_bindings(bindings, when)
            data = {'datasourceURI': self.gqe_uri, 'query': when, 'default-graph-uri': self.input_graph, 'skipCache':'true'}
            url = f"https://{self.url}:{self.port}/sparql?format=application/sparql-results+json"
            return manage_anzo_response(requests.post(url=url,
                                                      auth=(self.username, self.password),
                                                      data=data,
                                                      verify=False))
        except (ConnectionError, TimeoutError, ConnectTimeout):
            raise

    def execute_construct(self, given: Graph, when: str, bindings: dict = None) -> Graph:
        try:
            self.clear_graph()
            self.upload_given(given)
            if bindings:
                when = query_with_bindings(bindings, when)
            data = {'datasourceURI': self.gqe_uri, 'query': when, 'default-graph-uri': self.input_graph, 'skipCache':'true'}
            url = f"https://{self.url}:{self.port}/sparql?format=ttl"
            return Graph().parse(data=manage_anzo_response(requests.post(url=url,
                                                                         auth=(self.username, self.password),
                                                                         data=data,
                                                                         verify=False)))
        except (ConnectionError, TimeoutError, ConnectTimeout):
            raise

    # Get Given or then from the content of a graphmart
    def get_spec_component_from_graphmart(self, graphmart, layer=None):
        return self.anzo_client.query_graphmart(graphmart=graphmart, data_layers=layer,
                                                query_string="CONSTRUCT {?s ?p ?o} WHERE {?s ?p ?o}",
                                                skip_cache=True).as_quad_store()

    def get_query_from_querybuilder(self, folder_name, query_name):
        query = f"""SELECT ?query WHERE {{
            graph ?queryFolder {{
                ?bookmark a <http://www.cambridgesemantics.com/ontologies/QueryPlayground#QueryBookmark>;
                            <http://openanzo.org/ontologies/2008/07/System#query> ?query;
                            <http://purl.org/dc/elements/1.1/title> "{query_name}"
                }}
                ?queryFolder a <http://www.cambridgesemantics.com/ontologies/QueryPlayground#QueryFolder>;
                            <http://purl.org/dc/elements/1.1/title> "{folder_name}"
        }}"""
        return self.anzo_client.query_journal(query_string=query).as_table_results().as_record_dictionaries()[0].get(
            "query")

    def get_query_from_step(self, query_step_uri):
        query = f"""SELECT ?query WHERE {{
            BIND(<{query_step_uri}> as ?stepUri)
            graph ?stepUri {{
                ?stepUri a <http://cambridgesemantics.com/ontologies/Graphmarts#Step>;
                <http://cambridgesemantics.com/ontologies/Graphmarts#transformQuery> ?query
            }}
        }}
        """
        return self.anzo_client.query_journal(query_string=query).as_table_results().as_record_dictionaries()[0].get(
            "query")

    def upload_given(self, given: Graph):
        try:
            serialized_given = given.serialize(format="nt")
            insert_query = f"INSERT DATA {{graph <{self.input_graph}>{{{serialized_given}}}}}"
            data = {'datasourceURI': self.gqe_uri, 'update': insert_query}
            response = requests.post(url=f"https://{self.url}:{self.port}/sparql",
                                     auth=(self.username, self.password), data=data, verify=False)
            manage_anzo_response(response)
        except (ConnectionError, TimeoutError, ConnectTimeout):
            raise

    def clear_graph(self):
        try:
            clear_query = f"CLEAR GRAPH <{self.input_graph}>"
            data = {'datasourceURI': self.gqe_uri, 'update': clear_query}
            response = requests.post(url=f"https://{self.url}:{self.port}/sparql",
                                     auth=(self.username, self.password), data=data, verify=False)
            manage_anzo_response(response)
        except (ConnectionError, TimeoutError, ConnectTimeout):
            raise
