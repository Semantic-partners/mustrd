from dataclasses import dataclass
from rdflib import Graph, BNode, URIRef, Literal


@dataclass
class Given:
    graph: Graph


@dataclass
class When:
    query: str


@dataclass
class Then:
    graph: Graph


def run_test(g: Given, w: When) -> Then:
    result = g.graph.query(w.query)
    g = Graph()
    for pos, row in enumerate(result, 1):
        row_node = BNode()
        g.add((row_node, URIRef("http://www.w3.org/ns/shacl#order"), Literal(pos)))
        results = row.asdict().items()
        for key, value in results:
            column_node = BNode()
            g.add((row_node, URIRef("https://semanticpartners.com/mustrd/results"), column_node))
            g.add((column_node, URIRef("https://semanticpartners.com/mustrd/variable"), Literal(key)))
            g.add((column_node, URIRef("https://semanticpartners.com/mustrd/binding"), value))

    return Then(g)
