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

    def execute_select(self, given, when):
        self.clear_graph()
        self.upload_given(given)
        url = f"{self.graphDbUrl}:{self.graphDbPort}/repositories/{self.repository}?query={when}"
        return manage_graphdb_response(requests.post(url=url,
                                                          auth=(self.username, self.password)))

    def execute_construct(self, given, when):
        self.upload_given(given)
        url = f"{self.graphDbUrl}:{self.graphDbPort}/repositories/{self.repository}?query={when}"
        return Graph().parse(data=manage_graphdb_response(requests.get(url=url,
                                                                       auth=(self.username, self.password))))

    # https://github.com/Semantic-partners/mustrd/issues/22
    def upload_given(self, given):
        insert_query = f"INSERT DATA {{graph <{self.inputGraph}>{{{given}}}}}"
        requests.post(
            url=f"{self.graphDbUrl}:{self.graphDbPort}/repositories/{self.repository}/statements?update={insert_query}",
            auth=(self.username, self.password))

    def clear_graph(self):
        clear_query = f"CLEAR GRAPH <{self.inputGraph}>"
        requests.post(
            url=f"{self.graphDbUrl}:{self.graphDbPort}/repositories/{self.repository}/statements?update={clear_query}",
            auth=(self.username, self.password))
