import requests
from rdflib import Graph


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
        return self.manage_graphdb_response(requests.post(url=url,
                                                          auth=(self.username, self.password)))

    def execute_construct(self, given, when):
        self.upload_given(given)
        url = f"{self.graphDbUrl}:{self.graphDbPort}/repositories/{self.repository}?query={when}"
        return Graph().parse(data=self.manage_graphdb_response(requests.get(url=url,
                                                                             auth=(self.username, self.password))))

    # TODO put in body for longer input files
    def upload_given(self, given):
        insertQuery = f"INSERT DATA {{graph <{self.inputGraph}>{{{given}}}}}"
        requests.post(url=f"{self.graphDbUrl}:{self.graphDbPort}/repositories/{self.repository}/statements?update={insertQuery}", auth=(self.username, self.password))

    def clear_graph(self):
        clearQuery = f"CLEAR GRAPH <{self.inputGraph}>"
        requests.post(url=f"{self.graphDbUrl}:{self.graphDbPort}/repositories/{self.repository}/statements?update={clearQuery}", auth=(self.username, self.password))

    def manage_graphdb_response(self, response):
        contentString = response.content.decode("utf-8")
        if response.status_code == 200:
            return contentString
        else:
            raise Exception(f"GraphDb error, status code: {response.status_code}, content: {contentString}")
