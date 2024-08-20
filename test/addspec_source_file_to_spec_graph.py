from mustrd.namespace import MUST
from rdflib import Graph, Literal, URIRef

def parse_spec(spec: str, spec_uri: URIRef, filename: str):
        spec_graph = Graph().parse(data=spec, format='ttl')

        addspec_source_file_to_spec_graph(spec_graph, spec_uri, filename)
        return spec_graph

def addspec_source_file_to_spec_graph(spec_graph: Graph, spec_uri: URIRef, filename: str):
        spec_graph.add([spec_uri, MUST.specSourceFile, Literal(filename)])