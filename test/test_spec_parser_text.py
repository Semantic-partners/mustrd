import pandas

from mustrd import get_spec_component
from rdflib import Graph
from rdflib.namespace import Namespace
from namespace import MUST

TEST_DATA = Namespace("https://semanticpartners.com/data/test/")


class TestSpecParserTest:

    select_spec_uri = TEST_DATA.a_complete_select_spec
    select_spec = f"""
                @prefix rdf:       <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
                @prefix sh:        <http://www.w3.org/ns/shacl#> .
                @prefix must:      <https://mustrd.com/model/> .
                @prefix test-data: <https://semanticpartners.com/data/test/> .

                <{select_spec_uri}>
                    a          must:TestSpec ;
                    must:tripleStoreConfig [a must:rdfLibConfig];

                    must:hasGiven [a must:given;
                                must:dataSource [ a must:textDataSource ;
                                    must:text "<https://semanticpartners.com/data/test/sub><https://semanticpartners.com/data/test/pred><https://semanticpartners.com/data/test/obj>" 
                                ];];

                    must:hasWhen  [a must:when;
                                must:dataSource [ a must:textDataSource ;
                                    must:text "select ?s ?p ?o {{ ?s ?p ?o }}" 
                                ];
                                must:queryType must:SelectSparql
                    ] ;

                    must:hasThen [a must:then;
                                must:dataSource [ a must:textDataSource ;
                                    must:text \"""s,s_datatype,p,p_datatype,o,o_datatype\nhttps://semanticpartners.com/data/test/sub,http://www.w3.org/2001/XMLSchema#anyURI,https://semanticpartners.com/data/test/pred,http://www.w3.org/2001/XMLSchema#anyURI,https://semanticpartners.com/data/test/obj,http://www.w3.org/2001/XMLSchema#anyURI\"""
                        ];].

            """

    def test_given(self):
        spec_graph = Graph()
        spec_graph.parse(data=self.select_spec, format='ttl')

        given = get_spec_component(subject=self.select_spec_uri,
                                predicate=MUST.hasGiven,
                                spec_graph=spec_graph)

        assert given.value == "<https://semanticpartners.com/data/test/sub><https://semanticpartners.com/data/test/pred><https://semanticpartners.com/data/test/obj>"

    def test_when_select(self):
        spec_graph = Graph()
        spec_graph.parse(data=self.select_spec, format='ttl')
        when = get_spec_component(subject=self.select_spec_uri,
                                predicate=MUST.hasWhen,
                                spec_graph=spec_graph)

        expected_query = "select ?s ?p ?o { ?s ?p ?o }"

        assert when.value == expected_query
        assert when.queryType == MUST.SelectSparql

    def test_then_select(self):
        spec_graph = Graph()
        spec_graph.parse(data=self.select_spec, format='ttl')

        get_then = get_spec_component(subject=self.select_spec_uri,
                                predicate=MUST.hasThen,
                                spec_graph=spec_graph)

        expected_csv = """s,s_datatype,p,p_datatype,o,o_datatype
https://semanticpartners.com/data/test/sub,http://www.w3.org/2001/XMLSchema#anyURI,https://semanticpartners.com/data/test/pred,http://www.w3.org/2001/XMLSchema#anyURI,https://semanticpartners.com/data/test/obj,http://www.w3.org/2001/XMLSchema#anyURI"""
        assert get_then.value == expected_csv

    construct_spec_uri = TEST_DATA.a_construct_spec
    construct_spec = f"""@prefix rdf:       <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
                        @prefix sh:        <http://www.w3.org/ns/shacl#> .
                        @prefix must:      <https://mustrd.com/model/> .
                        @prefix test-data: <https://semanticpartners.com/data/test/> .

                        <{construct_spec_uri}>
                            a          must:TestSpec ;
                            must:tripleStoreConfig [a must:rdfLibConfig];

                            must:hasGiven [a must:given;
                                        must:dataSource [ a must:textDataSource ;
                                        must:text "<https://semanticpartners.com/data/test/sub><https://semanticpartners.com/data/test/pred><https://semanticpartners.com/data/test/obj>"
                                ];];

                            must:hasWhen  [a must:when;
                                        must:dataSource [ a must:textDataSource ;
                                            must:text "CONSTRUCT {{?s ?p ?o}} WHERE {{?s ?p ?o}}"
                                        ];
                                        must:queryType must:ConstructSparql
                            ] ;

                            must:hasThen [a must:then;
                                        must:dataSource [ a must:textDataSource ;
                                        must:text "<https://semanticpartners.com/data/test/sub><https://semanticpartners.com/data/test/pred><https://semanticpartners.com/data/test/obj>"
                                ];] ."""

    def test_when_construct(self):
        spec_graph = Graph()
        spec_graph.parse(data=self.construct_spec, format='ttl')

        when = get_spec_component(subject=self.construct_spec_uri,
                                predicate=MUST.hasWhen,
                                spec_graph=spec_graph)

        expected_query = "CONSTRUCT {?s ?p ?o} WHERE {?s ?p ?o}"

        print(when.value)
        print(expected_query)
        assert when.value == expected_query
        assert when.queryType == MUST.ConstructSparql

    def test_then_construct(self):
        spec_graph = Graph()
        spec_graph.parse(data=self.construct_spec, format='ttl')
        then = get_spec_component(subject=self.construct_spec_uri,
                                predicate=MUST.hasThen,
                                spec_graph=spec_graph)

        expected_graph = Graph()
        expected_graph.add((TEST_DATA.obj, TEST_DATA.sub, TEST_DATA.pred))

        expected_triples = """<https://semanticpartners.com/data/test/sub><https://semanticpartners.com/data/test/pred><https://semanticpartners.com/data/test/obj>"""
        assert then.value == expected_triples

