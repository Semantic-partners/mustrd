from dataclasses import dataclass
from rdflib import Graph, BNode, Literal, URIRef
from rdflib.namespace import SH, DefinedNamespace, Namespace

class MUSTRD(DefinedNamespace):
    _NS = Namespace("https://semanticpartners.com/mustrd/")

    results: URIRef
    variable: URIRef
    binding: URIRef


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
        g.add((row_node, SH.order, Literal(pos)))
        results = row.asdict().items()
        for key, value in results:
            column_node = BNode()
            g.add((row_node, MUSTRD.results, column_node))
            g.add((column_node, MUSTRD.variable, Literal(key)))
            g.add((column_node, MUSTRD.binding, value))

    return Then(g)
