from rdflib import URIRef
from rdflib.namespace import DefinedNamespace, Namespace


class MUST(DefinedNamespace):
    _NS = Namespace("https://mustrd.com/model/")

    results: URIRef
    variable: URIRef
    binding: URIRef
    query: URIRef
    given: URIRef
    when: URIRef
    then: URIRef
    TestSpec: URIRef
    SelectSparql: URIRef
    ConstructSparql: URIRef
    StatementsDataset: URIRef
    statements: URIRef
