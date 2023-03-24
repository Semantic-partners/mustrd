import requests
from rdflib import Graph


def manage_graphdb_response(response):
    content_string = response.content.decode("utf-8")
    if response.status_code == 200:
        return content_string
    else:
        raise Exception(f"GraphDb error, status code: {response.status_code}, content: {content_string}")


class MustrdGraphDb:
    def __init__(self, graphDbUrl, graphDbPort, graphDbRepository, inputGraph, username=None, password=None):
        self.graphDbUrl = graphDbUrl
        self.graphDbPort = graphDbPort
        self.username = username
        self.password = password
        self.repository = graphDbRepository
        self.inputGraph = inputGraph

    def execute_select(self, given, when, bindings: dict = None):
        self.clear_graph()
        self.upload_given(given)
        url = f"{self.graphDbUrl}:{self.graphDbPort}/repositories/{self.repository}"
        return manage_graphdb_response(requests.post(url=url,
                                                          auth=(self.username, self.password),data = when,  
                                                          headers = {'Content-Type': 'application/sparql-query', 'Accept': 'application/sparql-results+json'}))

    def execute_construct(self, given, when, bindings: dict = None):
        self.upload_given(given)
        url = f"{self.graphDbUrl}:{self.graphDbPort}/repositories/{self.repository}?query={when}"
        return Graph().parse(data=manage_graphdb_response(requests.get(url=url,
                                                                       auth=(self.username, self.password))))

    # https://github.com/Semantic-partners/mustrd/issues/22
    def upload_given(self, given: Graph):
        try:
            url = f"{self.graphDbUrl}:{self.graphDbPort}/repositories/{self.repository}/rdf-graphs/service?graph={self.inputGraph}"
            return requests.put(url=url,
                                                            auth=(self.username, self.password),data = given.serialize(format="ttl"),
                                                            headers = {'Content-Type': 'text/turtle'})
        except ConnectionError:
            raise

    def clear_graph(self):
        clear_query = f"CLEAR GRAPH <{self.inputGraph}>"
        requests.post(
            url=f"{self.graphDbUrl}:{self.graphDbPort}/repositories/{self.repository}/statements?update={clear_query}",
            auth=(self.username, self.password))
