from rdflib import URIRef
from rdflib.namespace import DefinedNamespace, Namespace


class MUST(DefinedNamespace):
    _NS = Namespace("https://mustrd.com/model/")

    TestSpec: URIRef
    given: URIRef
    when: URIRef
    then: URIRef
    query: URIRef
    bindings: URIRef
    SelectSparql: URIRef
    ConstructSparql: URIRef

    StatementsDataset: URIRef
    statements: URIRef

    TableDataset: URIRef
    rows: URIRef
    row: URIRef
    variable: URIRef
    binding: URIRef

    EmptyResult: URIRef
