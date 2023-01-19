import pandas

from mustrd import get_spec_component
from rdflib import Graph
from rdflib.namespace import Namespace
from namespace import MUST
from rdflib.compare import isomorphic, graph_diff

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
                           must:dataSource [
                                a must:StatementsDataSource ;
                                must:statements [a rdf:Statement ;
                                rdf:subject test-data:sub ;
                                rdf:predicate test-data:pred ;
                                rdf:object test-data:obj ;
                            ] ;]; ];

                    must:hasWhen  [a must:when;
                                must:dataSource [ a must:textDataSource ;
                                    must:text "select ?s ?p ?o {{ ?s ?p ?o }}" 
                                ];
                                must:queryType must:SelectSparql
                    ] ;

                    must:hasThen [a must:then;
                                must:dataSource [a must:TableDataSource ;
                                must:rows [ sh:order 1 ;
                                            must:row [
                                            must:variable "s" ;
                                            must:binding test-data:sub ; 
                                                ] ,
                                                [
                                            must:variable "p" ;
                                            must:binding test-data:pred ; 
                                                ] ,
                                                [
                                            must:variable "o" ;
                                            must:binding test-data:obj  ; 
                                                ];
                    ] ;];].
            """

    def test_given(self):
        
        spec_graph = Graph()
        spec_graph.parse(data=self.select_spec, format='ttl')

        given = get_spec_component(subject=self.select_spec_uri,
                                predicate=MUST.hasGiven,
                                spec_graph=spec_graph)
        assert self.compare_graphs(given.value, "@prefix ns1: <https://semanticpartners.com/data/test/> .ns1:sub ns1:pred ns1:obj .")

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

        expected_csv = """{"results": {"bindings": [{"binding": {"type": "uri", "value": "https://semanticpartners.com/data/test/sub"}, "variable": {"type": "literal", "value": "s"}}, {"binding": {"type": "uri", "value": "https://semanticpartners.com/data/test/pred"}, "variable": {"type": "literal", "value": "p"}}, {"binding": {"type": "uri", "value": "https://semanticpartners.com/data/test/obj"}, "variable": {"type": "literal", "value": "o"}}]}, "head": {"vars": ["then", "order", "variable", "binding"]}}"""
        assert get_then.value == expected_csv

    construct_spec_uri = TEST_DATA.a_construct_spec
    construct_spec = f"""                
                @prefix rdf:       <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
                @prefix sh:        <http://www.w3.org/ns/shacl#> .
                @prefix must:      <https://mustrd.com/model/> .
                @prefix test-data: <https://semanticpartners.com/data/test/> .

                <{construct_spec_uri}>
                    a          must:TestSpec ;
                    must:tripleStoreConfig [a must:rdfLibConfig];

                    must:hasGiven [a must:given;
                           must:dataSource [
                                a must:StatementsDataSource ;
                                must:statements [a rdf:Statement ;
                                rdf:subject test-data:sub ;
                                rdf:predicate test-data:pred ;
                                rdf:object test-data:obj ;
                            ] ;]; ];

                    must:hasWhen  [a must:when;
                                must:dataSource [ a must:textDataSource ;
                                    must:text "CONSTRUCT {{?s ?p ?o}} WHERE {{?s ?p ?o}}"
                                ];
                                must:queryType must:ConstructSparql
                    ] ;

                    must:hasThen [a must:given;
                           must:dataSource [
                                a must:StatementsDataSource ;
                                must:statements [a rdf:Statement ;
                                rdf:subject test-data:sub ;
                                rdf:predicate test-data:pred ;
                                rdf:object test-data:obj ;
                            ] ;]; ].
                            """

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

        #expected_triples = """<https://semanticpartners.com/data/test/sub><https://semanticpartners.com/data/test/pred><https://semanticpartners.com/data/test/obj>"""
        assert self.compare_graphs(then.value, "@prefix ns1: <https://semanticpartners.com/data/test/> .ns1:sub ns1:pred ns1:obj .")

    def compare_graphs(self, actualTtlStr, expectedTtlStr):
        actual_graph = Graph()
        actual_graph.parse(data=actualTtlStr, format='ttl')

        expected_graph = Graph()
        expected_graph.parse(data=expectedTtlStr, format='ttl')
        return isomorphic(actual_graph, expected_graph)


