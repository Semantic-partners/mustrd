import requests
from pyanzo import AnzoClient
from rdflib import Graph


class MustrdAnzo:
    def __init__(self, anzoUrl, anzoPort, gqeURI, inputGraph,  username=None, password=None):
        self.anzoUrl = anzoUrl
        self.anzoPort = anzoPort
        self.username = username
        self.password = password
        self.gqeURI = gqeURI
        self.inputGraph = inputGraph
        self.anzo_client = AnzoClient(self.anzoUrl, self.anzoPort, self.username, self.password)

    # Get Given or then from the content of a graphmart
    def getSpecspecComponentGraphmart(self, graphMart, layer=None):
            return self.anzo_client.query_graphmart(graphmart=graphMart, data_layers=layer,
            query_string="CONSTRUCT {?s ?p ?o} WHERE {?s ?p ?o}", skip_cache=True).as_quad_store()

    def getQueryFromQueryBuilder(self, folderName, queryName):
        query = f"""SELECT ?query WHERE {{
            graph ?queryFolder {{
                ?bookmark a <http://www.cambridgesemantics.com/ontologies/QueryPlayground#QueryBookmark>;
                            <http://openanzo.org/ontologies/2008/07/System#query> ?query;
                            <http://purl.org/dc/elements/1.1/title> "{queryName}"
                }}
                ?queryFolder a <http://www.cambridgesemantics.com/ontologies/QueryPlayground#QueryFolder>;
                            <http://purl.org/dc/elements/1.1/title> "{folderName}"
        }}"""
        return self.anzo_client.query_journal(query_string=query).as_table_results().as_record_dictionaries()[0].get("query")

    def getQueryFromStep(self, queryStepUri):
        query = f"""SELECT ?query WHERE {{
            BIND(<{queryStepUri}> as ?stepUri)
            graph ?stepUri {{
                ?stepUri a <http://cambridgesemantics.com/ontologies/Graphmarts#Step>;
                <http://cambridgesemantics.com/ontologies/Graphmarts#transformQuery> ?query
            }}
        }}
        """
        return self.anzo_client.query_journal(query_string=query).as_table_results().as_record_dictionaries()[0].get("query")

    def upload_given(self, given):
        insertQuery = f"INSERT DATA {{graph <{self.inputGraph}>{{{given}}}}}"
        data = {'datasourceURI' : self.gqeURI, 'update' : insertQuery}
        requests.post(url=f"https://{self.anzoUrl}:{self.anzoPort}/sparql", auth=(self.username, self.password), data=data)

    def clear_graph(self):
        clearQuery = f"CLEAR GRAPH <{self.inputGraph}>"
        data = {'datasourceURI' : self.gqeURI, 'update' : clearQuery}
        requests.post(url=f"https://{self.anzoUrl}:{self.anzoPort}/sparql", auth=(self.username, self.password), data=data)

    def execute_select(self, given, when):
        self.clear_graph()
        self.upload_given(given)
        data = {'datasourceURI' : self.gqeURI, 'query': when, 'default-graph-uri' : self.inputGraph}
        return requests.post(url=f"https://{self.anzoUrl}:{self.anzoPort}/sparql?format=application/sparql-results+json",
                                auth=(self.username, self.password), data=data).content.decode("utf-8")
    
    def execute_construct(self, given, when):
        self.upload_given(given)
        data = {'datasourceURI' : self.gqeURI, 'query': when, 'default-graph-uri' : self.inputGraph}
        return Graph().parse(data=requests.post(url=f"https://{self.anzoUrl}:{self.anzoPort}/sparql?format=ttl",
        auth=(self.username, self.password), data=data).content.decode("utf-8"))
