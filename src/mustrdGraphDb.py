import requests
from pyparsing import ParseException
from rdflib import Graph
from requests import ConnectionError


# https://github.com/Semantic-partners/mustrd/issues/72
def manage_graphdb_response(response) -> str:
    content_string = response.content.decode("utf-8")
    if response.status_code == 200:
        return content_string
    elif response.status_code == 204:
        pass
    else:
        raise Exception(f"GraphDb error, status code: {response.status_code}, content: {content_string}")


class MustrdGraphDb:
    def __init__(self, graphdb_url, graphdb_port, graphdb_repository, input_graph=None, username=None, password=None):
        self.url = graphdb_url
        self.port = graphdb_port
        self.username = username
        self.password = password
        self.repository = graphdb_repository
        self.input_graph = input_graph

    def execute_select(self, given: Graph, when: str, bindings: dict = None) -> str:
        if "where {" not in when.lower():
            raise ParseException(pstr='GraphDB Implementation: No WHERE clause in query.')
        try:
            if self.input_graph is None:
                self.drop_default_graph()
            else:
                self.clear_graph()
                split_when = when.lower().split("where {", 1)
                when = split_when[0] + "where { GRAPH <" + self.input_graph + "> {" + split_when[1] + "}"
            self.upload_given(given)
            bindings_string = ""
            if bindings:
                for key, value in bindings.items():
                    bindings_string += f'&${key}="{value}"'
            url = f"{self.url}:{self.port}/repositories/{self.repository}?query={when}{bindings_string}"
            headers = {
                'Accept': 'application/sparql-results+json'
            }
            return manage_graphdb_response(requests.request("GET",
                                                            url=url,
                                                            headers=headers))
        except ConnectionError:
            raise

    def execute_construct(self, given: Graph, when: str, bindings: dict = None) -> Graph:
        if "where {" not in when.lower():
            raise ParseException(pstr='GraphDB Implementation: No WHERE clause in query.')
        try:
            if self.input_graph is None:
                self.drop_default_graph()
            else:
                self.clear_graph()
                split_when = when.lower().split("where {", 1)
                when = split_when[0] + "where { GRAPH <" + self.input_graph + "> {" + split_when[1] + "}"
            self.upload_given(given)
            bindings_string = ""
            if bindings:
                for key, value in bindings.items():
                    bindings_string += f'&${key}="{value}"'
            url = f"{self.url}:{self.port}/repositories/{self.repository}?query={when}{bindings_string}"
            return Graph().parse(data=manage_graphdb_response(requests.get(url=url,
                                                                           auth=(self.username, self.password))))
        except ConnectionError:
            raise

    # https://github.com/Semantic-partners/mustrd/issues/22
    def upload_given(self, given: Graph):
        try:
            serialized_given = given.serialize(format="nt")
            if self.input_graph is None:
                insert_query = f"INSERT DATA {{ {serialized_given} }}"
            else:
                insert_query = f"INSERT DATA {{graph <{self.input_graph}>{{{serialized_given}}}}}"
            response = requests.post(
                url=f"{self.url}:{self.port}/repositories/{self.repository}/statements?update={insert_query}",
                auth=(self.username, self.password))
            manage_graphdb_response(response)
        except ConnectionError:
            raise

    def clear_graph(self):
        try:
            clear_query = f"CLEAR GRAPH <{self.input_graph}>"
            response = requests.post(
                url=f"{self.url}:{self.port}/repositories/{self.repository}/statements?update={clear_query}",
                auth=(self.username, self.password))
            manage_graphdb_response(response)
        except ConnectionError:
            raise

    def drop_default_graph(self):
        try:
            clear_query = "DROP DEFAULT"
            response = requests.post(
                url=f"{self.url}:{self.port}/repositories/{self.repository}/statements?update={clear_query}",
                auth=(self.username, self.password))
            manage_graphdb_response(response)
        except ConnectionError:
            raise
