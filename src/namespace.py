from rdflib import URIRef
from rdflib.namespace import DefinedNamespace, Namespace


class MUST(DefinedNamespace):
    _NS = Namespace("https://mustrd.com/model/")

    #Main
    TestSpec: URIRef
    tripleStoreConfig: URIRef
    inputGraph: URIRef
    rdfLibConfig: URIRef
    rdfLib: URIRef
    anzo: URIRef
    graphDb: URIRef
    dataSource:  URIRef
    file: URIRef
    filename: URIRef
    queryFolder: URIRef
    queryName: URIRef
    dataSourceUrl: URIRef
    text: URIRef
    queryType: URIRef
    given: URIRef
    when: URIRef
    then: URIRef
    query: URIRef
    bindings: URIRef
    SelectSparql: URIRef
    ConstructSparql: URIRef
    UpdateSparql: URIRef

    statements: URIRef

    # specification data sources
    TableDataSource: URIRef
    StatementsDataSource: URIRef
    FileDataSource: URIRef
    HttpDataSource: URIRef
    TextDataSource: URIRef
    FolderDataSource: URIRef
    EmptyGraphResult: URIRef
    EmptyTableResult: URIRef

    rows: URIRef
    row: URIRef
    variable: URIRef
    binding: URIRef


    # runner uris
    fileSource: URIRef
    loadedFromFile: URIRef

    # config parameters
    url: URIRef
    port: URIRef
    username: URIRef
    password: URIRef
    inputGraph: URIRef
    repository: URIRef

    #Anzo
    anzoConfig: URIRef
    anzoGraphmartDataSource: URIRef
    graphmart: URIRef
    layer: URIRef
    anzoQueryBuilderDataSource: URIRef
    gqeURI: URIRef

    #GraphDb
    graphDbConfig: URIRef

