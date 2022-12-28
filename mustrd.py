from dataclasses import dataclass
from rdflib import Graph, BNode, Literal, URIRef
from rdflib.namespace import SH, DefinedNamespace, Namespace


class MUST(DefinedNamespace):
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


def run_scenario(g: Given, w: When) -> Then:
    result = g.graph.query(w.query)
    g = Graph()
    for pos, row in enumerate(result, 1):
        row_node = BNode()
        g.add((row_node, SH.order, Literal(pos)))
        results = row.asdict().items()
        for key, value in results:
            column_node = BNode()
            g.add((row_node, MUST.results, column_node))
            g.add((column_node, MUST.variable, Literal(key)))
            g.add((column_node, MUST.binding, value))

    return Then(g)
