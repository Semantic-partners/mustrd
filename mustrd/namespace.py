from rdflib import URIRef
from rdflib.namespace import DefinedNamespace, Namespace


# Namespace for the test specifications
class MUST(DefinedNamespace):
    _NS = Namespace("https://mustrd.org/model/")

    # Specification classes
    TestSpec: URIRef
    SelectSparql: URIRef
    ConstructSparql: URIRef
    UpdateSparql: URIRef
    AnzoQueryDrivenUpdateSparql: URIRef
    AskSparql: URIRef
    DescribeSparql: URIRef
    SpadeEdnGroupSource: URIRef
    
    # Specification properties
    given: URIRef
    when: URIRef
    then: URIRef
    dataSource: URIRef
    file: URIRef
    fileurl: URIRef
    fileName: URIRef
    queryFolder: URIRef
    queryName: URIRef
    dataSourceUrl: URIRef
    queryText: URIRef
    queryType: URIRef
    hasStatement: URIRef
    hasRow: URIRef
    hasBinding: URIRef
    variable: URIRef
    boundValue: URIRef
    focus: URIRef

    # Specification data sources
    TableDataset: URIRef
    StatementsDataset: URIRef
    FileDataset: URIRef
    HttpDataset: URIRef
    TextSparqlSource: URIRef
    FileSparqlSource: URIRef
    FolderSparqlSource: URIRef
    FolderDataset: URIRef
    EmptyGraph: URIRef
    EmptyTable: URIRef
    InheritedDataset: URIRef

    # runner uris
    fileSource: URIRef
    loadedFromFile: URIRef
    specSourceFile: URIRef
    specFileName: URIRef

    # Triple store config parameters
    # Anzo
    AnzoGraphmartDataset: URIRef
    AnzoQueryBuilderSparqlSource: URIRef
    AnzoGraphmartStepSparqlSource: URIRef
    AnzoGraphmartLayerSparqlSource: URIRef
    AnzoGraphmartQueryDrivenTemplatedStepSparqlSource: URIRef
    anzoQueryStep: URIRef
    anzoGraphmartLayer: URIRef

    graphmart: URIRef
    layer: URIRef

    # FIXME: There is nothing to do that by default?
    @classmethod
    def get_local_name(cls, uri: URIRef):
        return str(uri).split(cls._NS)[1]


# Namespace for triplestores
class TRIPLESTORE(DefinedNamespace):
    _NS = Namespace("https://mustrd.org/triplestore/")
    RdfLib: URIRef
    GraphDb: URIRef
    Anzo: URIRef
    ExternalTripleStore: URIRef
    InternalTripleStore: URIRef

    gqeURI: URIRef
    inputGraph: URIRef
    outputGraph: URIRef  # anzo specials?     # Triple store config parameters
    url: URIRef
    port: URIRef
    username: URIRef
    password: URIRef
    repository: URIRef


# namespace for pytest_mustrd config
class MUSTRDTEST(DefinedNamespace):
    _NS = Namespace("https://mustrd.org/mustrdTest/")
    MustrdTest: URIRef
    hasSpecPath: URIRef
    hasDataPath: URIRef
    triplestoreSpecPath: URIRef
    hasPytestPath: URIRef
    filterOnTripleStore: URIRef

from rdflib import Namespace

MUST = Namespace("https://mustrd.org/model/")

# Add SpadeEdnGroupSource to the namespace
MUST.SpadeEdnGroupSource = MUST["SpadeEdnGroupSource"]
