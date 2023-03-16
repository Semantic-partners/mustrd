from rdflib import URIRef
from rdflib.namespace import DefinedNamespace, Namespace


class MUST(DefinedNamespace):
    _NS = Namespace("https://mustrd.com/model/")

    #Main
    TestSpec: URIRef
    tripleStoreConfig: URIRef
    inputGraph: URIRef
    rdfLibConfig: URIRef
    dataSource:  URIRef
    FileDataSource: URIRef
    file: URIRef
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
    hasGiven: URIRef
    hasWhen: URIRef
    hasThen: URIRef
    query: URIRef
    bindings: URIRef
    SelectSparql: URIRef
    ConstructSparql: URIRef
    UpdateSparql: URIRef

    StatementsDataset: URIRef
    statements: URIRef

    TableDataSource: URIRef
    StatementsDataSource: URIRef
    TableDataset: URIRef
    rows: URIRef
    row: URIRef
    variable: URIRef
    binding: URIRef

    EmptyGraphResult: URIRef
    EmptyTableResult: URIRef

    #Anzo
    anzoConfig: URIRef
    anzoURL: URIRef
    anzoPort: URIRef
    anzoUser: URIRef
    anzoPassword: URIRef
    anzoGraphmartDataSource: URIRef
    graphmart: URIRef
    layer: URIRef
    anzoQueryBuilderDataSource: URIRef
    gqeURI: URIRef

    #GraphDb
    graphDbConfig: URIRef
    graphDbUrl: URIRef
    graphDbPort: URIRef
    graphDbUser: URIRef
    graphDbPassword: URIRef
    graphDbRepo: URIRef
