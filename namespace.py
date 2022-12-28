from rdflib import URIRef
from rdflib.namespace import DefinedNamespace, Namespace


class MUST(DefinedNamespace):
    _NS = Namespace("https://semanticpartners.com/mustrd/")

    results: URIRef
    variable: URIRef
    binding: URIRef
