from rdflib import URIRef
from rdflib.namespace import DefinedNamespace, Namespace


class MUST(DefinedNamespace):
    _NS = Namespace("https://mustrd.com/model/")

    TestSpec: URIRef
    tripleStoreConfig: URIRef
    anzoConfig: URIRef
    anzoURL: URIRef
    anzoPort: URIRef
    anzoUser: URIRef
    anzoPassword: URIRef
    gqeURI: URIRef
    inputGraph: URIRef
    rdfLibConfig: URIRef
    FileDataSource: URIRef
    file: URIRef
    anzoGraphmartDataSource: URIRef
    graphmart: URIRef
    layer: URIRef
    anzoQueryBuilderDataSource: URIRef
    queryFolder: URIRef
    queryName: URIRef
    HttpDataSource: URIRef
    dataSourceUrl: URIRef
    textDataSource: URIRef
    text: URIRef
    queryType: URIRef
    given: URIRef
    when: URIRef
    then: URIRef
    query: URIRef
    SelectSparql: URIRef
    ConstructSparql: URIRef

    StatementsDataset: URIRef
    statements: URIRef

    TableDataset: URIRef
    rows: URIRef
    row: URIRef
    variable: URIRef
    binding: URIRef
