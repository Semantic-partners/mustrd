from rdflib import URIRef
from rdflib.namespace import DefinedNamespace, Namespace


class MUST(DefinedNamespace):
    _NS = Namespace("https://mustrd.com/model/")

    # Specification classes
    TestSpec: URIRef
    SelectSparql: URIRef
    ConstructSparql: URIRef
    UpdateSparql: URIRef
    AskSparql: URIRef
    DescribeSparql: URIRef

    # Specification properties
    given: URIRef
    when: URIRef
    then: URIRef
    inputGraph: URIRef
    dataSource: URIRef
    file: URIRef
    fileName: URIRef
    queryFolder: URIRef
    queryName: URIRef
    dataSourceUrl: URIRef
    queryText: URIRef
    queryType: URIRef
    bindings: URIRef
    statements: URIRef
    rows: URIRef
    row: URIRef
    variable: URIRef
    binding: URIRef

    # Specification data sources
    TableDataSource: URIRef
    StatementsDataSource: URIRef
    FileDataSource: URIRef
    HttpDataSource: URIRef
    TextDataSource: URIRef
    FolderDataSource: URIRef
    EmptyGraphResult: URIRef
    EmptyTableResult: URIRef

    # runner uris
    fileSource: URIRef
    loadedFromFile: URIRef

    # Triple store config parameters
    url: URIRef
    port: URIRef
    username: URIRef
    password: URIRef
    inputGraph: URIRef
    repository: URIRef

    # RDFLib
    RdfLib: URIRef
    RdfLibConfig: URIRef

    # Anzo
    Anzo: URIRef
    AnzoConfig: URIRef
    AnzoGraphmartDataSource: URIRef
    AnzoQueryBuilderDataSource: URIRef
    graphmart: URIRef
    layer: URIRef
    gqeURI: URIRef

    # GraphDb
    GraphDb: URIRef
    GraphDbConfig: URIRef
