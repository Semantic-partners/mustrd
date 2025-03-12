"""
MIT License

Copyright (c) 2023 Semantic Partners Ltd

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

from rdflib import URIRef
from rdflib.namespace import DefinedNamespace, Namespace


# Namespace for the test specifications
class MUST(DefinedNamespace):
    _NS = Namespace("https://mustrd.com/model/")

    # Specification classes
    TestSpec: URIRef
    SelectSparql: URIRef
    ConstructSparql: URIRef
    UpdateSparql: URIRef
    AnzoQueryDrivenUpdateSparql: URIRef
    AskSparql: URIRef
    DescribeSparql: URIRef

    # Specification properties
    given: URIRef
    when: URIRef
    then: URIRef
    dataSource: URIRef
    file: URIRef
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
    _NS = Namespace("https://mustrd.com/triplestore/")
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
    _NS = Namespace("https://mustrd.com/mustrdTest/")
    MustrdTest: URIRef
    hasSpecPath: URIRef
    hasDataPath: URIRef
    triplestoreSpecPath: URIRef
    hasPytestPath: URIRef
    filterOnTripleStore: URIRef
