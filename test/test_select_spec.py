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

import os

from rdflib import Graph
from rdflib.namespace import Namespace
from rdflib.term import Literal, Variable, URIRef

from pathlib import Path

from mustrd import run_select_spec, SpecPassed, SelectSpecFailure, SparqlParseFailure, \
    SpecPassedWithWarning
from namespace import MUST
from spec_component import get_spec_component_from_file, TableThenSpec, parse_spec_component
from src.utils import get_project_root

TEST_DATA = Namespace("https://semanticpartners.com/data/test/")


class TestRunSelectSpec:
    given_sub_pred_obj = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        test-data:sub test-data:pred test-data:obj .
        """

    triple_store = {"type": MUST.RdfLib}

    def test_select_spec_passes(self):
        state = Graph()
        state.parse(data=self.given_sub_pred_obj, format="ttl")
        select_query = """
        select ?s ?p ?o { ?s ?p ?o }
        """
        spec_graph = Graph()
        spec = """
        @prefix sh: <http://www.w3.org/ns/shacl#> .
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        
        test-data:my_first_spec 
            a must:TestSpec ;
            must:then  [ a must:TableDataset ;
                                   must:hasRow [ must:hasBinding[
                                        must:variable "s" ;
                                        must:boundValue  test-data:sub ; ],
                                      [ must:variable "p" ;
                                        must:boundValue  test-data:pred ; ],
                                      [ must:variable "o" ;
                                        must:boundValue  test-data:obj ; ] ; ] ;
               ] .
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_first_spec

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              folder_location=None,
                                              mustrd_triple_store=self.triple_store)

        t = run_select_spec(spec_uri, state, select_query, then_component.value, self.triple_store)

        expected_result = SpecPassed(spec_uri, self.triple_store["type"])
        assert t == expected_result
        assert type(then_component) == TableThenSpec

    def test_select_spec_fails_with_expected_vs_actual_table_comparison(self):
        state = Graph()
        state.parse(data=self.given_sub_pred_obj, format="ttl")
        select_query = """
        select ?s ?p ?o { ?s ?p ?o }
        """
        spec_graph = Graph()
        spec = """
        @prefix sh: <http://www.w3.org/ns/shacl#> .
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        
        test-data:my_failing_spec 
            a must:TestSpec ;
            must:then  [ a must:TableDataset ;
                        must:hasRow [ must:hasBinding[
                                       must:variable "s" ;
                                       must:boundValue test-data:wrong-subject ; 
                                        ] ,
                                        [
                                       must:variable "p" ;
                                       must:boundValue test-data:pred ; 
                                        ] ,
                                        [
                                       must:variable "o" ;
                                       must:boundValue test-data:obj  ; 
                                        ]; ] ;
                ].
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_spec

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              folder_location=None,
                                              mustrd_triple_store=self.triple_store)

        spec_result = run_select_spec(spec_uri, state, select_query, then_component.value, self.triple_store)

        if type(spec_result) == SelectSpecFailure:
            table_diff = spec_result.table_comparison.to_markdown()
            assert type(then_component) == TableThenSpec
            assert spec_result.spec_uri == spec_uri
            assert table_diff == """|    | ('s', 'expected')                                    | ('s', 'actual')                            |
|---:|:-----------------------------------------------------|:-------------------------------------------|
|  0 | https://semanticpartners.com/data/test/wrong-subject | https://semanticpartners.com/data/test/sub |"""
        else:
            raise Exception(f"wrong spec result type {spec_result}")

    def test_select_spec_fails_for_different_types(self):
        triples = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        test-data:sub test-data:pred 1 .
        """
        state = Graph()
        state.parse(data=triples, format="ttl")

        select_query = """
        select ?s ?p ?o { ?s ?p ?o }
        """
        spec_graph = Graph()
        spec = """
        @prefix sh: <http://www.w3.org/ns/shacl#> .
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        
        test-data:my_failing_spec 
            a must:TestSpec ;
            must:then  [ a must:TableDataset ;
                        must:hasRow [ must:hasBinding[
                                       must:variable "s" ;
                                       must:boundValue test-data:sub ; 
                                        ] ,
                                        [
                                       must:variable "p" ;
                                       must:boundValue test-data:pred ; 
                                        ] ,
                                        [
                                       must:variable "o" ;
                                       must:boundValue 1.0  ; 
                                        ]; ] ;
                ].
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_spec

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              folder_location=None,
                                              mustrd_triple_store=self.triple_store)

        spec_result = run_select_spec(spec_uri, state, select_query, then_component.value, self.triple_store)

        if type(spec_result) == SelectSpecFailure:
            table_diff = spec_result.table_comparison.to_markdown()
            assert type(then_component) == TableThenSpec
            assert spec_result.spec_uri == spec_uri
            assert table_diff == """|    |   ('o', 'expected') |   ('o', 'actual') | ('o_datatype', 'expected')               | ('o_datatype', 'actual')                 |
|---:|--------------------:|------------------:|:-----------------------------------------|:-----------------------------------------|
|  0 |                   1 |                 1 | http://www.w3.org/2001/XMLSchema#decimal | http://www.w3.org/2001/XMLSchema#integer |"""
        else:
            raise Exception(f"wrong spec result type {spec_result}")

    def test_select_spec_fails_for_different_types_where_one_is_string(self):
        triples = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        test-data:sub test-data:pred 1 .
        """
        state = Graph()
        state.parse(data=triples, format="ttl")

        select_query = """
        select ?s ?p ?o { ?s ?p ?o }
        """
        spec_graph = Graph()
        spec = """
        @prefix sh: <http://www.w3.org/ns/shacl#> .
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        
        test-data:my_failing_spec 
            a must:TestSpec ;
            must:then  [ a must:TableDataset ;
                        must:hasRow [ must:hasBinding[
                                       must:variable "s" ;
                                       must:boundValue test-data:sub ; 
                                        ] ,
                                        [
                                       must:variable "p" ;
                                       must:boundValue test-data:pred ; 
                                        ] ,
                                        [
                                       must:variable "o" ;
                                       must:boundValue "1"  ; 
                                        ]; ] ;
                 ].
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_spec

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              folder_location=None,
                                              mustrd_triple_store=self.triple_store)

        spec_result = run_select_spec(spec_uri, state, select_query, then_component.value, self.triple_store)

        if type(spec_result) == SelectSpecFailure:
            table_diff = spec_result.table_comparison.to_markdown()
            assert type(then_component) == TableThenSpec
            assert spec_result.spec_uri == spec_uri
            assert table_diff == """|    | ('o_datatype', 'expected')              | ('o_datatype', 'actual')                 |
|---:|:----------------------------------------|:-----------------------------------------|
|  0 | http://www.w3.org/2001/XMLSchema#string | http://www.w3.org/2001/XMLSchema#integer |"""
        else:
            raise Exception(f"wrong spec result type {spec_result}")

    def test_invalid_select_statement_spec_fails(self):
        state = Graph()
        state.parse(data=self.given_sub_pred_obj, format="ttl")
        select_query = """select ?s ?p ?o { typo }"""
        spec_graph = Graph()
        spec = """
        @prefix sh: <http://www.w3.org/ns/shacl#> .
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        
        test-data:my_failing_spec 
            a must:TestSpec ;
            must:then  [ a must:TableDataset ;
                        must:hasRow [ must:hasBinding[
                                       must:variable "s" ;
                                       must:boundValue test-data:wrong-subject ; 
                                        ] ; ] ;
                ].
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_spec

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              folder_location=None,
                                              mustrd_triple_store=self.triple_store)

        spec_result = run_select_spec(spec_uri, state, select_query, then_component.value, self.triple_store)

        if type(spec_result) == SparqlParseFailure:
            assert type(then_component) == TableThenSpec
            assert spec_result.spec_uri == spec_uri
            assert str(
                spec_result.exception) == "Expected {SelectQuery | ConstructQuery | DescribeQuery | AskQuery}, found 'typo'  (at char 18), (line:1, col:19)"
        else:
            raise Exception(f"wrong spec result type {spec_result}")

    def test_select_with_variables_spec_passes(self):
        triples = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        test-data:sub test-data:pred "hello world" .
        """
        state = Graph()
        state.parse(data=triples, format="ttl")

        select_query = """
        select ?s ?p ?o { ?s ?p ?o }
        """
        binding = {Variable('o'): Literal('hello world')}
        spec_graph = Graph()
        spec = """
        @prefix sh: <http://www.w3.org/ns/shacl#> .
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .

        test-data:my_first_spec 
            a must:TestSpec ;
            must:then  [ a must:TableDataset ;
                        must:hasRow [ must:hasBinding[
                                       must:variable "s" ;
                                       must:boundValue test-data:sub ; 
                                        ] ,
                                        [
                                       must:variable "p" ;
                                       must:boundValue test-data:pred ; 
                                        ] ,
                                        [
                                       must:variable "o" ;
                                       must:boundValue "hello world"  ; 
                                        ]; ] ;
                         ].
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_first_spec

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              folder_location=None,
                                              mustrd_triple_store=self.triple_store)

        spec_result = run_select_spec(spec_uri, state, select_query, then_component.value, self.triple_store,
                                      bindings=binding)

        expected_result = SpecPassed(spec_uri, self.triple_store["type"])
        assert spec_result == expected_result
        assert type(then_component) == TableThenSpec

    def test_select_with_variables_spec_fails_with_expected_vs_actual_table_comparison(self):
        triples = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        test-data:sub test-data:pred "hello world" .
        """
        state = Graph()
        state.parse(data=triples, format="ttl")

        select_query = """
        select ?s ?p ?o { ?s ?p ?o }
        """
        binding = {Variable('o'): Literal('hello world')}

        spec_graph = Graph()
        spec = """
        @prefix sh: <http://www.w3.org/ns/shacl#> .
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .

        test-data:my_failing_spec 
            a must:TestSpec ;
            must:then  [ a must:TableDataset ;
                        must:hasRow [ must:hasBinding[
                                       must:variable "s" ;
                                       must:boundValue test-data:sub ; 
                                        ] ,
                                        [
                                       must:variable "p" ;
                                       must:boundValue test-data:pred ; 
                                        ] ,
                                        [
                                       must:variable "o" ;
                                       must:boundValue "hello worlds"  ; 
                                        ]; ] ;
                 ].
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_spec

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              folder_location=None,
                                              mustrd_triple_store=self.triple_store)

        spec_result = run_select_spec(spec_uri, state, select_query, then_component.value, self.triple_store,
                                      bindings=binding)

        if type(spec_result) == SelectSpecFailure:
            table_diff = spec_result.table_comparison.to_markdown()
            assert type(then_component) == TableThenSpec
            assert spec_result.spec_uri == spec_uri
            assert table_diff == """|    | ('o', 'expected')   | ('o', 'actual')   |
|---:|:--------------------|:------------------|
|  0 | hello worlds        | hello world       |"""
        else:
            raise Exception(f"wrong spec result type {spec_result}")

    def test_select_spec_expect_empty_result_passes(self):
        state = Graph()
        state.parse(data=self.given_sub_pred_obj, format="ttl")
        select_query = """
        select ?a ?b ?c { ?s ?p ?o }
        """
        spec_graph = Graph()
        spec = """
        @prefix sh: <http://www.w3.org/ns/shacl#> .
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .

        test-data:my_first_spec 
            a must:TestSpec ;
            must:then  [ a must:EmptyTable ] .
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_first_spec

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              folder_location=None,
                                              mustrd_triple_store=self.triple_store)

        spec_result = run_select_spec(spec_uri, state, select_query, then_component.value, self.triple_store)

        expected_result = SpecPassed(spec_uri, self.triple_store["type"])
        assert type(then_component) == TableThenSpec
        assert spec_result == expected_result

    def test_select_spec_expect_empty_result_fails(self):
        state = Graph()
        state.parse(data=self.given_sub_pred_obj, format="ttl")
        select_query = """
        select ?s ?p ?o { ?s ?p ?o }
        """
        spec_graph = Graph()
        spec = """
                @prefix sh: <http://www.w3.org/ns/shacl#> .
                @prefix must: <https://mustrd.com/model/> .
                @prefix test-data: <https://semanticpartners.com/data/test/> .

                test-data:my_failing_spec
                    a must:TestSpec ;
                    must:then  [ a must:EmptyTable ] .
                """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_spec

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              folder_location=None,
                                              mustrd_triple_store=self.triple_store)

        spec_result = run_select_spec(spec_uri, state, select_query, then_component.value, self.triple_store)

        print(spec_result)
        if type(spec_result) == SelectSpecFailure:
            table_diff = spec_result.table_comparison.to_markdown()
            assert type(then_component) == TableThenSpec
            assert spec_result.spec_uri == spec_uri
            assert table_diff == """|    | ('s', 'expected')   | ('s', 'actual')                            | ('s_datatype', 'expected')   | ('s_datatype', 'actual')                | ('p', 'expected')   | ('p', 'actual')                             | ('p_datatype', 'expected')   | ('p_datatype', 'actual')                | ('o', 'expected')   | ('o', 'actual')                            | ('o_datatype', 'expected')   | ('o_datatype', 'actual')                |
|---:|:--------------------|:-------------------------------------------|:-----------------------------|:----------------------------------------|:--------------------|:--------------------------------------------|:-----------------------------|:----------------------------------------|:--------------------|:-------------------------------------------|:-----------------------------|:----------------------------------------|
|  0 |                     | https://semanticpartners.com/data/test/sub |                              | http://www.w3.org/2001/XMLSchema#anyURI |                     | https://semanticpartners.com/data/test/pred |                              | http://www.w3.org/2001/XMLSchema#anyURI |                     | https://semanticpartners.com/data/test/obj |                              | http://www.w3.org/2001/XMLSchema#anyURI |"""
        else:
            raise Exception(f"wrong spec result type {spec_result}")

    def test_select_spec_unexpected_empty_result_fails(self):
        state = Graph()
        state.parse(data=self.given_sub_pred_obj, format="ttl")
        select_query = """
        select ?a ?b ?c { ?s ?p ?o }
        """
        spec_graph = Graph()
        spec = """
        @prefix sh: <http://www.w3.org/ns/shacl#> .
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .

        test-data:my_failing_spec
            a must:TestSpec ;
            must:then  [ a must:TableDataset ;
                        must:hasRow [ must:hasBinding[
                                       must:variable "s" ;
                                       must:boundValue test-data:sub ; 
                                        ] ,
                                        [
                                       must:variable "p" ;
                                       must:boundValue test-data:pred ; 
                                        ] ,
                                        [
                                       must:variable "o" ;
                                       must:boundValue test-data:obj  ; 
                                        ]; ] ;
                         ].
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_spec

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              folder_location=None,
                                              mustrd_triple_store=self.triple_store)

        spec_result = run_select_spec(spec_uri, state, select_query, then_component.value, self.triple_store)

        print(spec_result)
        if type(spec_result) == SelectSpecFailure:
            table_diff = spec_result.table_comparison.to_markdown()
            assert type(then_component) == TableThenSpec
            assert spec_result.spec_uri == spec_uri
            assert table_diff == """|    | ('s', 'expected')                          | ('s', 'actual')   | ('s_datatype', 'expected')              | ('s_datatype', 'actual')   | ('p', 'expected')                           | ('p', 'actual')   | ('p_datatype', 'expected')              | ('p_datatype', 'actual')   | ('o', 'expected')                          | ('o', 'actual')   | ('o_datatype', 'expected')              | ('o_datatype', 'actual')   |
|---:|:-------------------------------------------|:------------------|:----------------------------------------|:---------------------------|:--------------------------------------------|:------------------|:----------------------------------------|:---------------------------|:-------------------------------------------|:------------------|:----------------------------------------|:---------------------------|
|  0 | https://semanticpartners.com/data/test/sub |                   | http://www.w3.org/2001/XMLSchema#anyURI |                            | https://semanticpartners.com/data/test/pred |                   | http://www.w3.org/2001/XMLSchema#anyURI |                            | https://semanticpartners.com/data/test/obj |                   | http://www.w3.org/2001/XMLSchema#anyURI |                            |"""
        else:
            raise Exception(f"wrong spec result type {spec_result}")

    def test_select_with_different_types_of_variables_spec_passes(self):
        triples = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        test-data:sub test-data:pred true .
        """
        state = Graph()
        state.parse(data=triples, format="ttl")

        select_query = """
        select ?s ?p ?o { ?s ?p ?o }
        """
        binding = {Variable('s'): URIRef("https://semanticpartners.com/data/test/sub"), Variable('o'): Literal(True)}
        spec_graph = Graph()
        spec = """
        @prefix sh: <http://www.w3.org/ns/shacl#> .
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .

        test-data:my_first_spec 
            a must:TestSpec ;
            must:then  [ a must:TableDataset ;
                        must:hasRow [ must:hasBinding[
                                       must:variable "s" ;
                                       must:boundValue test-data:sub ; 
                                        ] ,
                                        [
                                       must:variable "p" ;
                                       must:boundValue test-data:pred ; 
                                        ] ,
                                        [
                                       must:variable "o" ;
                                       must:boundValue true  ; 
                                        ]; ] ;
                         ].
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_first_spec

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              folder_location=None,
                                              mustrd_triple_store=self.triple_store)

        spec_result = run_select_spec(spec_uri, state, select_query, then_component.value, self.triple_store,
                                      bindings=binding)

        expected_result = SpecPassed(spec_uri, self.triple_store["type"])
        assert spec_result == expected_result
        assert type(then_component) == TableThenSpec

    def test_select_spec_different_types_of_variables_spec_fails(self):
        triples = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        test-data:sub test-data:pred test-data:obj , 25 .
        """
        state = Graph()
        state.parse(data=triples, format="ttl")

        select_query = """
        select ?o { ?s ?p ?o }
        """
        binding = {Variable('o'): Literal(25)}
        spec_graph = Graph()
        spec = """
        @prefix sh: <http://www.w3.org/ns/shacl#> .
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .

        test-data:my_failing_spec
            a must:TestSpec ;
            must:then  [ a must:TableDataset ;
                        must:hasRow [ must:hasBinding
                                        [
                                       must:variable "o" ;
                                       must:boundValue 25.0  ; 
                                        ]; ] ;
                         ].
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_spec

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              folder_location=None,
                                              mustrd_triple_store=self.triple_store)

        spec_result = run_select_spec(spec_uri, state, select_query, then_component.value, self.triple_store,
                                      bindings=binding)

        print(spec_result)
        if type(spec_result) == SelectSpecFailure:
            table_diff = spec_result.table_comparison.to_markdown()
            assert type(then_component) == TableThenSpec
            assert spec_result.spec_uri == spec_uri
            assert table_diff == """|    |   ('o', 'expected') |   ('o', 'actual') | ('o_datatype', 'expected')               | ('o_datatype', 'actual')                 |
|---:|--------------------:|------------------:|:-----------------------------------------|:-----------------------------------------|
|  0 |                  25 |                25 | http://www.w3.org/2001/XMLSchema#decimal | http://www.w3.org/2001/XMLSchema#integer |"""
        else:
            raise Exception(f"wrong spec result type {spec_result}")

    def test_select_spec_multiline_then_passes(self):
        triples = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        test-data:sub test-data:pred test-data:obj , test-data:object .
        """
        state = Graph()
        state.parse(data=triples, format="ttl")

        select_query = """
        select ?s ?p ?o { ?s ?p ?o }
        """
        spec_graph = Graph()
        spec = """
        @prefix sh: <http://www.w3.org/ns/shacl#> .
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .

        test-data:my_first_spec 
            a must:TestSpec ;
            must:then  [ a must:TableDataset ;
                        must:hasRow [ must:hasBinding[
                                       must:variable "s" ;
                                       must:boundValue test-data:sub ; 
                                        ] ,
                                        [
                                       must:variable "p" ;
                                       must:boundValue test-data:pred ; 
                                        ] ,
                                        [
                                       must:variable "o" ;
                                       must:boundValue test-data:obj  ; 
                                        ]; ] ,
                                    [ must:hasBinding[
                                       must:variable "s" ;
                                       must:boundValue test-data:sub ; 
                                        ] ,
                                        [
                                       must:variable "p" ;
                                       must:boundValue test-data:pred ; 
                                        ] ,
                                        [
                                       must:variable "o" ;
                                       must:boundValue test-data:object ; 
                                        ]; ] ; ].
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_first_spec

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              folder_location=None,
                                              mustrd_triple_store=self.triple_store)

        spec_result = run_select_spec(spec_uri, state, select_query, then_component.value, self.triple_store)

        expected_result = SpecPassed(spec_uri, self.triple_store["type"])
        assert spec_result == expected_result
        assert type(then_component) == TableThenSpec

    def test_select_spec_expected_fewer_columns_fails(self):
        state = Graph()
        state.parse(data=self.given_sub_pred_obj, format="ttl")
        select_query = """
        select ?s ?p ?o { ?s ?p ?o }
        """
        spec_graph = Graph()
        spec = """
        @prefix sh: <http://www.w3.org/ns/shacl#> .
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .

        test-data:my_failing_spec
            a must:TestSpec ;
            must:then  [ a must:TableDataset ;
                        must:hasRow [ must:hasBinding[
                                       must:variable "s" ;
                                       must:boundValue test-data:sub ; 
                                        ] ,
                                        [
                                       must:variable "o" ;
                                       must:boundValue test-data:obj  ; 
                                        ]; ] ;
                         ].
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_spec

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              folder_location=None,
                                              mustrd_triple_store=self.triple_store)

        spec_result = run_select_spec(spec_uri, state, select_query, then_component.value, self.triple_store)

        print(spec_result)
        if type(spec_result) == SelectSpecFailure:
            table_diff = spec_result.table_comparison.to_markdown()
            message = spec_result.message
            assert type(then_component) == TableThenSpec
            assert spec_result.spec_uri == spec_uri
            assert message == "Expected 1 row(s) and 2 column(s), got 1 row(s) and 3 column(s)"
            assert table_diff == """|    | ('s', 'expected')                          | ('s', 'actual')                            | ('s_datatype', 'expected')              | ('s_datatype', 'actual')                | ('o', 'expected')                          | ('o', 'actual')                            | ('o_datatype', 'expected')              | ('o_datatype', 'actual')                | ('p', 'expected')   | ('p', 'actual')                             | ('p_datatype', 'expected')   | ('p_datatype', 'actual')                |
|---:|:-------------------------------------------|:-------------------------------------------|:----------------------------------------|:----------------------------------------|:-------------------------------------------|:-------------------------------------------|:----------------------------------------|:----------------------------------------|:--------------------|:--------------------------------------------|:-----------------------------|:----------------------------------------|
|  0 | https://semanticpartners.com/data/test/sub | https://semanticpartners.com/data/test/sub | http://www.w3.org/2001/XMLSchema#anyURI | http://www.w3.org/2001/XMLSchema#anyURI | https://semanticpartners.com/data/test/obj | https://semanticpartners.com/data/test/obj | http://www.w3.org/2001/XMLSchema#anyURI | http://www.w3.org/2001/XMLSchema#anyURI |                     | https://semanticpartners.com/data/test/pred |                              | http://www.w3.org/2001/XMLSchema#anyURI |"""
        else:
            raise Exception(f"wrong spec result type {spec_result}")

    def test_select_spec_expected_more_columns_fails(self):
        state = Graph()
        state.parse(data=self.given_sub_pred_obj, format="ttl")
        select_query = """
        select ?s ?p { ?s ?p ?o }
        """
        spec_graph = Graph()
        spec = """
        @prefix sh: <http://www.w3.org/ns/shacl#> .
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .

        test-data:my_failing_spec
            a must:TestSpec ;
            must:then  [ a must:TableDataset ;
                        must:hasRow [ must:hasBinding[
                                       must:variable "s" ;
                                       must:boundValue test-data:sub ; 
                                        ] ,
                                        [
                                       must:variable "p" ;
                                       must:boundValue test-data:pred  ; 
                                        ] ,
                                        [
                                       must:variable "o" ;
                                       must:boundValue test-data:obj  ; 
                                        ]; ] ;
                         ].
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_spec

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              folder_location=None,
                                              mustrd_triple_store=self.triple_store)

        spec_result = run_select_spec(spec_uri, state, select_query, then_component.value, self.triple_store)

        print(spec_result)
        if type(spec_result) == SelectSpecFailure:
            table_diff = spec_result.table_comparison.to_markdown()
            message = spec_result.message
            assert type(then_component) == TableThenSpec
            assert spec_result.spec_uri == spec_uri
            assert message == "Expected 1 row(s) and 3 column(s), got 1 row(s) and 2 column(s)"
            assert table_diff == """|    | ('s', 'expected')                          | ('s', 'actual')                            | ('s_datatype', 'expected')              | ('s_datatype', 'actual')                | ('p', 'expected')                           | ('p', 'actual')                             | ('p_datatype', 'expected')              | ('p_datatype', 'actual')                | ('o', 'expected')                          | ('o', 'actual')   | ('o_datatype', 'expected')              | ('o_datatype', 'actual')   |
|---:|:-------------------------------------------|:-------------------------------------------|:----------------------------------------|:----------------------------------------|:--------------------------------------------|:--------------------------------------------|:----------------------------------------|:----------------------------------------|:-------------------------------------------|:------------------|:----------------------------------------|:---------------------------|
|  0 | https://semanticpartners.com/data/test/sub | https://semanticpartners.com/data/test/sub | http://www.w3.org/2001/XMLSchema#anyURI | http://www.w3.org/2001/XMLSchema#anyURI | https://semanticpartners.com/data/test/pred | https://semanticpartners.com/data/test/pred | http://www.w3.org/2001/XMLSchema#anyURI | http://www.w3.org/2001/XMLSchema#anyURI | https://semanticpartners.com/data/test/obj |                   | http://www.w3.org/2001/XMLSchema#anyURI |                            |"""
        else:
            raise Exception(f"wrong spec result type {spec_result}")

    def test_select_spec_expected_fewer_and_different_columns_fails(self):
        state = Graph()
        state.parse(data=self.given_sub_pred_obj, format="ttl")
        select_query = """
        select ?s ?p ?o { ?s ?p ?o }
        """
        spec_graph = Graph()
        spec = """
        @prefix sh: <http://www.w3.org/ns/shacl#> .
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .

        test-data:my_failing_spec
            a must:TestSpec ;
            must:then  [ a must:TableDataset ;
                        must:hasRow [ must:hasBinding[
                                       must:variable "s" ;
                                       must:boundValue test-data:sub ; 
                                        ] ,
                                        [
                                       must:variable "obj" ;
                                       must:boundValue test-data:object  ; 
                                        ]; ] ;
                         ].
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_spec

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              folder_location=None,
                                              mustrd_triple_store=self.triple_store)

        spec_result = run_select_spec(spec_uri, state, select_query, then_component.value, self.triple_store)

        print(spec_result)
        if type(spec_result) == SelectSpecFailure:
            table_diff = spec_result.table_comparison.to_markdown()
            message = spec_result.message
            assert type(then_component) == TableThenSpec
            assert spec_result.spec_uri == spec_uri
            assert message == "Expected 1 row(s) and 2 column(s), got 1 row(s) and 3 column(s)"
            assert table_diff == """|    | ('s', 'expected')                          | ('s', 'actual')                            | ('s_datatype', 'expected')              | ('s_datatype', 'actual')                | ('obj', 'expected')                           | ('obj', 'actual')   | ('obj_datatype', 'expected')            | ('obj_datatype', 'actual')   | ('o', 'expected')   | ('o', 'actual')                            | ('o_datatype', 'expected')   | ('o_datatype', 'actual')                | ('p', 'expected')   | ('p', 'actual')                             | ('p_datatype', 'expected')   | ('p_datatype', 'actual')                |
|---:|:-------------------------------------------|:-------------------------------------------|:----------------------------------------|:----------------------------------------|:----------------------------------------------|:--------------------|:----------------------------------------|:-----------------------------|:--------------------|:-------------------------------------------|:-----------------------------|:----------------------------------------|:--------------------|:--------------------------------------------|:-----------------------------|:----------------------------------------|
|  0 | https://semanticpartners.com/data/test/sub | https://semanticpartners.com/data/test/sub | http://www.w3.org/2001/XMLSchema#anyURI | http://www.w3.org/2001/XMLSchema#anyURI | https://semanticpartners.com/data/test/object |                     | http://www.w3.org/2001/XMLSchema#anyURI |                              |                     | https://semanticpartners.com/data/test/obj |                              | http://www.w3.org/2001/XMLSchema#anyURI |                     | https://semanticpartners.com/data/test/pred |                              | http://www.w3.org/2001/XMLSchema#anyURI |"""
        else:
            raise Exception(f"wrong spec result type {spec_result}")

    def test_select_spec_expected_fewer_rows_fails(self):
        triples = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        test-data:sub test-data:pred test-data:obj .
        test-data:subject test-data:predicate test-data:object .
        """
        state = Graph()
        state.parse(data=triples, format="ttl")

        select_query = """
        select ?s ?p ?o { ?s ?p ?o }
        """
        spec_graph = Graph()
        spec = """
        @prefix sh: <http://www.w3.org/ns/shacl#> .
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .

        test-data:my_failing_spec
            a must:TestSpec ;
            must:then  [ a must:TableDataset ;
                        must:hasRow [ must:hasBinding[
                                       must:variable "s" ;
                                       must:boundValue test-data:sub ; 
                                        ] ,
                                        [
                                       must:variable "p" ;
                                       must:boundValue test-data:pred ; 
                                        ] ,
                                        [
                                       must:variable "o" ;
                                       must:boundValue test-data:obj  ; 
                                        ]; ] ;
                         ].
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_spec

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              folder_location=None,
                                              mustrd_triple_store=self.triple_store)

        spec_result = run_select_spec(spec_uri, state, select_query, then_component.value, self.triple_store)

        print(spec_result)
        if type(spec_result) == SelectSpecFailure:
            table_diff = spec_result.table_comparison.to_markdown()
            message = spec_result.message
            assert type(then_component) == TableThenSpec
            assert spec_result.spec_uri == spec_uri
            assert message == "Expected 1 row(s) and 3 column(s), got 2 row(s) and 3 column(s)"
            assert table_diff == """|    | ('s', 'expected')   | ('s', 'actual')                                | ('s_datatype', 'expected')   | ('s_datatype', 'actual')                | ('p', 'expected')   | ('p', 'actual')                                  | ('p_datatype', 'expected')   | ('p_datatype', 'actual')                | ('o', 'expected')   | ('o', 'actual')                               | ('o_datatype', 'expected')   | ('o_datatype', 'actual')                |
|---:|:--------------------|:-----------------------------------------------|:-----------------------------|:----------------------------------------|:--------------------|:-------------------------------------------------|:-----------------------------|:----------------------------------------|:--------------------|:----------------------------------------------|:-----------------------------|:----------------------------------------|
|  0 |                     | https://semanticpartners.com/data/test/subject |                              | http://www.w3.org/2001/XMLSchema#anyURI |                     | https://semanticpartners.com/data/test/predicate |                              | http://www.w3.org/2001/XMLSchema#anyURI |                     | https://semanticpartners.com/data/test/object |                              | http://www.w3.org/2001/XMLSchema#anyURI |"""
        else:
            raise Exception(f"wrong spec result type {spec_result}")

    def test_select_spec_expected_more_rows_fails(self):
        state = Graph()
        state.parse(data=self.given_sub_pred_obj, format="ttl")
        select_query = """
        select ?s ?p ?o { ?s ?p ?o }
        """
        spec_graph = Graph()
        spec = """
        @prefix sh: <http://www.w3.org/ns/shacl#> .
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .

        test-data:my_failing_spec
            a must:TestSpec ;
            must:then [ a must:TableDataset ;
                        must:hasRow [ must:hasBinding[
                                       must:variable "s" ;
                                       must:boundValue test-data:sub ; 
                                        ] ,
                                        [
                                       must:variable "p" ;
                                       must:boundValue test-data:pred  ; 
                                        ] ,
                                        [
                                       must:variable "o" ;
                                       must:boundValue test-data:obj  ; 
                                        ]; ] ,
                                   [ must:hasBinding[
                                       must:variable "s" ;
                                       must:boundValue test-data:subject ; 
                                        ] ,
                                        [
                                       must:variable "p" ;
                                       must:boundValue test-data:predicate  ; 
                                        ] ,
                                        [
                                       must:variable "o" ;
                                       must:boundValue test-data:object  ; 
                                        ]; ] ;    
                          ].
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_spec

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              folder_location=None,
                                              mustrd_triple_store=self.triple_store)

        spec_result = run_select_spec(spec_uri, state, select_query, then_component.value, self.triple_store)

        print(spec_result)
        if type(spec_result) == SelectSpecFailure:
            table_diff = spec_result.table_comparison.to_markdown()
            message = spec_result.message
            assert type(then_component) == TableThenSpec
            assert spec_result.spec_uri == spec_uri
            assert message == "Expected 2 row(s) and 3 column(s), got 1 row(s) and 3 column(s)"
            assert table_diff == """|    | ('s', 'expected')                              | ('s', 'actual')   | ('s_datatype', 'expected')              | ('s_datatype', 'actual')   | ('p', 'expected')                                | ('p', 'actual')   | ('p_datatype', 'expected')              | ('p_datatype', 'actual')   | ('o', 'expected')                             | ('o', 'actual')   | ('o_datatype', 'expected')              | ('o_datatype', 'actual')   |
|---:|:-----------------------------------------------|:------------------|:----------------------------------------|:---------------------------|:-------------------------------------------------|:------------------|:----------------------------------------|:---------------------------|:----------------------------------------------|:------------------|:----------------------------------------|:---------------------------|
|  0 | https://semanticpartners.com/data/test/subject |                   | http://www.w3.org/2001/XMLSchema#anyURI |                            | https://semanticpartners.com/data/test/predicate |                   | http://www.w3.org/2001/XMLSchema#anyURI |                            | https://semanticpartners.com/data/test/object |                   | http://www.w3.org/2001/XMLSchema#anyURI |                            |"""
        else:
            raise Exception(f"wrong spec result type {spec_result}")

    def test_select_spec_expected_fewer_and_different_rows_fails(self):
        triples = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        test-data:sub1 test-data:pred1 test-data:obj1 .
        test-data:sub2 test-data:pred2 test-data:obj2 .
        test-data:sub3 test-data:pred3 test-data:obj3 .
        """
        state = Graph()
        state.parse(data=triples, format="ttl")

        select_query = """
        select ?s ?p ?o { ?s ?p ?o }
        """
        spec_graph = Graph()
        spec = """
        @prefix sh: <http://www.w3.org/ns/shacl#> .
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .

        test-data:my_failing_spec
            a must:TestSpec ;
            must:then  [ a must:TableDataset ;
                        must:hasRow [ must:hasBinding[
                                       must:variable "s" ;
                                       must:boundValue test-data:sub1 ; 
                                        ] ,
                                        [
                                       must:variable "p" ;
                                       must:boundValue test-data:pred1 ; 
                                        ] ,
                                        [
                                       must:variable "o" ;
                                       must:boundValue test-data:obj1  ; 
                                        ];  ] ,
                                    [ must:hasBinding[
                                       must:variable "s" ;
                                       must:boundValue test-data:sub4 ; 
                                        ] ,
                                        [
                                       must:variable "p" ;
                                       must:boundValue test-data:pred4 ; 
                                        ] ,
                                        [
                                       must:variable "o" ;
                                       must:boundValue test-data:obj4  ; 
                                        ]; ] ;
                         ].
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_spec

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              folder_location=None,
                                              mustrd_triple_store=self.triple_store)

        spec_result = run_select_spec(spec_uri, state, select_query, then_component.value, self.triple_store)

        print(spec_result)
        if type(spec_result) == SelectSpecFailure:
            table_diff = spec_result.table_comparison.to_markdown()
            message = spec_result.message
            assert type(then_component) == TableThenSpec
            assert spec_result.spec_uri == spec_uri
            assert message == "Expected 2 row(s) and 3 column(s), got 3 row(s) and 3 column(s)"
            assert table_diff == """|    | ('s', 'expected')                           | ('s', 'actual')                             | ('s_datatype', 'expected')              | ('s_datatype', 'actual')                | ('p', 'expected')                            | ('p', 'actual')                              | ('p_datatype', 'expected')              | ('p_datatype', 'actual')                | ('o', 'expected')                           | ('o', 'actual')                             | ('o_datatype', 'expected')              | ('o_datatype', 'actual')                |
|---:|:--------------------------------------------|:--------------------------------------------|:----------------------------------------|:----------------------------------------|:---------------------------------------------|:---------------------------------------------|:----------------------------------------|:----------------------------------------|:--------------------------------------------|:--------------------------------------------|:----------------------------------------|:----------------------------------------|
|  0 |                                             | https://semanticpartners.com/data/test/sub2 |                                         | http://www.w3.org/2001/XMLSchema#anyURI |                                              | https://semanticpartners.com/data/test/pred2 |                                         | http://www.w3.org/2001/XMLSchema#anyURI |                                             | https://semanticpartners.com/data/test/obj2 |                                         | http://www.w3.org/2001/XMLSchema#anyURI |
|  1 |                                             | https://semanticpartners.com/data/test/sub3 |                                         | http://www.w3.org/2001/XMLSchema#anyURI |                                              | https://semanticpartners.com/data/test/pred3 |                                         | http://www.w3.org/2001/XMLSchema#anyURI |                                             | https://semanticpartners.com/data/test/obj3 |                                         | http://www.w3.org/2001/XMLSchema#anyURI |
|  2 | https://semanticpartners.com/data/test/sub4 |                                             | http://www.w3.org/2001/XMLSchema#anyURI |                                         | https://semanticpartners.com/data/test/pred4 |                                              | http://www.w3.org/2001/XMLSchema#anyURI |                                         | https://semanticpartners.com/data/test/obj4 |                                             | http://www.w3.org/2001/XMLSchema#anyURI |                                         |"""
        else:
            raise Exception(f"wrong spec result type {spec_result}")

    def test_select_spec_with_optional_passes(self):
        triples = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        test-data:sub1 test-data:pred test-data:obj ; test-data:predicate test-data:object.
        test-data:sub2 test-data:pred test-data:obj .
        """
        state = Graph()
        state.parse(data=triples, format="ttl")

        select_query = """
        select ?s ?o ?object { ?s <https://semanticpartners.com/data/test/pred> ?o . OPTIONAL {?s <https://semanticpartners.com/data/test/predicate> ?object} }
        """
        spec_graph = Graph()
        spec = """
        @prefix sh: <http://www.w3.org/ns/shacl#> .
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .

        test-data:my_first_spec 
            a must:TestSpec ;
            must:then  [ a must:TableDataset ;
                 must:hasRow [ must:hasBinding[ must:variable "s" ;
                                        must:boundValue  test-data:sub1 ; ],
                                      [ must:variable "o" ;
                                        must:boundValue  test-data:obj ; ] ,
                                      [ must:variable "object" ;
                                        must:boundValue  test-data:object ; ] ; ] ,
                            [ must:hasBinding[ must:variable "s" ;
                                        must:boundValue  test-data:sub2 ; ],
                                      [ must:variable "o" ;
                                        must:boundValue  test-data:obj ; ]; ] ; ] .
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_first_spec

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              folder_location=None,
                                              mustrd_triple_store=self.triple_store)

        spec_result = run_select_spec(spec_uri, state, select_query, then_component.value, self.triple_store)

        expected_result = SpecPassed(spec_uri, self.triple_store["type"])
        assert spec_result == expected_result
        assert type(then_component) == TableThenSpec

    def test_select_spec_with_optional_fails_with_expected_vs_actual_table_comparison(self):
        triples = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        test-data:sub1 test-data:pred test-data:obj ; test-data:predicate test-data:object.
        test-data:sub2 test-data:pred test-data:obj .
        """
        state = Graph()
        state.parse(data=triples, format="ttl")

        select_query = """
                select ?s ?o ?object { ?s <https://semanticpartners.com/data/test/pred> ?o . OPTIONAL {?s <https://semanticpartners.com/data/test/predicate> ?object} }
                """

        spec_graph = Graph()
        spec = """
        @prefix sh: <http://www.w3.org/ns/shacl#> .
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .

        test-data:my_failing_spec
            a must:TestSpec ;
            must:then  [ a must:TableDataset ;
                 must:hasRow [ must:hasBinding[ must:variable "s" ;
                                        must:boundValue  test-data:sub1 ; ],
                                      [ must:variable "o" ;
                                        must:boundValue  test-data:obj ; ] ,
                                      [ must:variable "object" ;
                                        must:boundValue  test-data:object ; ] ; ] ,
                            [ must:hasBinding[ must:variable "s" ;
                                        must:boundValue  test-data:sub2 ; ],
                                      [ must:variable "o" ;
                                        must:boundValue  test-data:object ; ]; ] ; ] .
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_spec

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              folder_location=None,
                                              mustrd_triple_store=self.triple_store)

        spec_result = run_select_spec(spec_uri, state, select_query, then_component.value, self.triple_store)

        if type(spec_result) == SelectSpecFailure:
            table_diff = spec_result.table_comparison.to_markdown()
            message = spec_result.message
            assert type(then_component) == TableThenSpec
            assert spec_result.spec_uri == spec_uri
            assert message == "Expected 2 row(s) and 3 column(s), got 2 row(s) and 3 column(s)"
            assert table_diff == """|    | ('o', 'expected')                             | ('o', 'actual')                            |
|---:|:----------------------------------------------|:-------------------------------------------|
|  1 | https://semanticpartners.com/data/test/object | https://semanticpartners.com/data/test/obj |"""
        else:
            raise Exception(f"wrong spec result type {spec_result}")

    def test_select_spec_expected_different_column_names_fails(self):
        state = Graph()
        state.parse(data=self.given_sub_pred_obj, format="ttl")
        select_query = """
        select ?s ?p ?o { ?s ?p ?o }
        """
        spec_graph = Graph()
        spec = """
        @prefix sh: <http://www.w3.org/ns/shacl#> .
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .

        test-data:my_failing_spec
            a must:TestSpec ;
            must:then  [ a must:TableDataset ;
                        must:hasRow [ must:hasBinding[
                                       must:variable "s" ;
                                       must:boundValue test-data:sub ; 
                                        ] ,
                                        [
                                       must:variable "p" ;
                                       must:boundValue test-data:pred ; 
                                        ] ,
                                        [
                                       must:variable "obj" ;
                                       must:boundValue test-data:obj  ; 
                                        ]; ] ;
                         ].
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_spec

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              folder_location=None,
                                              mustrd_triple_store=self.triple_store)

        spec_result = run_select_spec(spec_uri, state, select_query, then_component.value, self.triple_store)

        print(spec_result)
        if type(spec_result) == SelectSpecFailure:
            table_diff = spec_result.table_comparison.to_markdown()
            message = spec_result.message
            assert type(then_component) == TableThenSpec
            assert spec_result.spec_uri == spec_uri
            assert message == "Expected 1 row(s) and 3 column(s), got 1 row(s) and 3 column(s)"
            assert table_diff == """|    | ('s', 'expected')                          | ('s', 'actual')                            | ('s_datatype', 'expected')              | ('s_datatype', 'actual')                | ('p', 'expected')                           | ('p', 'actual')                             | ('p_datatype', 'expected')              | ('p_datatype', 'actual')                | ('obj', 'expected')                        | ('obj', 'actual')   | ('obj_datatype', 'expected')            | ('obj_datatype', 'actual')   | ('o', 'expected')   | ('o', 'actual')                            | ('o_datatype', 'expected')   | ('o_datatype', 'actual')                |
|---:|:-------------------------------------------|:-------------------------------------------|:----------------------------------------|:----------------------------------------|:--------------------------------------------|:--------------------------------------------|:----------------------------------------|:----------------------------------------|:-------------------------------------------|:--------------------|:----------------------------------------|:-----------------------------|:--------------------|:-------------------------------------------|:-----------------------------|:----------------------------------------|
|  0 | https://semanticpartners.com/data/test/sub | https://semanticpartners.com/data/test/sub | http://www.w3.org/2001/XMLSchema#anyURI | http://www.w3.org/2001/XMLSchema#anyURI | https://semanticpartners.com/data/test/pred | https://semanticpartners.com/data/test/pred | http://www.w3.org/2001/XMLSchema#anyURI | http://www.w3.org/2001/XMLSchema#anyURI | https://semanticpartners.com/data/test/obj |                     | http://www.w3.org/2001/XMLSchema#anyURI |                              |                     | https://semanticpartners.com/data/test/obj |                              | http://www.w3.org/2001/XMLSchema#anyURI |"""
        else:
            raise Exception(f"wrong spec result type {spec_result}")

    def test_select_spec_expected_fewer_rows_and_columns_fails(self):
        triples = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        test-data:sub test-data:pred test-data:obj , test-data:object .
        """
        state = Graph()
        state.parse(data=triples, format="ttl")

        select_query = """
        select ?s ?p ?o { ?s ?p ?o }
        """
        spec_graph = Graph()
        spec = """
        @prefix sh: <http://www.w3.org/ns/shacl#> .
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .

        test-data:my_failing_spec
            a must:TestSpec ;
            must:then  [ a must:TableDataset ;
                        must:hasRow [ must:hasBinding[
                                       must:variable "s" ;
                                       must:boundValue test-data:sub ; 
                                        ] ,                                                                               [
                                       must:variable "o" ;
                                       must:boundValue test-data:obj  ; 
                                        ]; ] ;
                         ].
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_spec

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              folder_location=None,
                                              mustrd_triple_store=self.triple_store)

        spec_result = run_select_spec(spec_uri, state, select_query, then_component.value, self.triple_store)

        print(spec_result)
        if type(spec_result) == SelectSpecFailure:
            table_diff = spec_result.table_comparison.to_markdown()
            message = spec_result.message
            assert type(then_component) == TableThenSpec
            assert spec_result.spec_uri == spec_uri
            assert message == "Expected 1 row(s) and 2 column(s), got 2 row(s) and 3 column(s)"
            assert table_diff == """|    | ('s', 'expected')                          | ('s', 'actual')                            | ('s_datatype', 'expected')              | ('s_datatype', 'actual')                | ('o', 'expected')                          | ('o', 'actual')                               | ('o_datatype', 'expected')              | ('o_datatype', 'actual')                | ('p', 'expected')   | ('p', 'actual')                             | ('p_datatype', 'expected')   | ('p_datatype', 'actual')                |
|---:|:-------------------------------------------|:-------------------------------------------|:----------------------------------------|:----------------------------------------|:-------------------------------------------|:----------------------------------------------|:----------------------------------------|:----------------------------------------|:--------------------|:--------------------------------------------|:-----------------------------|:----------------------------------------|
|  0 |                                            | https://semanticpartners.com/data/test/sub |                                         | http://www.w3.org/2001/XMLSchema#anyURI |                                            | https://semanticpartners.com/data/test/obj    |                                         | http://www.w3.org/2001/XMLSchema#anyURI |                     | https://semanticpartners.com/data/test/pred |                              | http://www.w3.org/2001/XMLSchema#anyURI |
|  1 |                                            | https://semanticpartners.com/data/test/sub |                                         | http://www.w3.org/2001/XMLSchema#anyURI |                                            | https://semanticpartners.com/data/test/object |                                         | http://www.w3.org/2001/XMLSchema#anyURI |                     | https://semanticpartners.com/data/test/pred |                              | http://www.w3.org/2001/XMLSchema#anyURI |
|  2 | https://semanticpartners.com/data/test/sub |                                            | http://www.w3.org/2001/XMLSchema#anyURI |                                         | https://semanticpartners.com/data/test/obj |                                               | http://www.w3.org/2001/XMLSchema#anyURI |                                         |                     |                                             |                              |                                         |"""
        else:
            raise Exception(f"wrong spec result type {spec_result}")

    def test_select_spec_expected_fewer_and_different_rows_and_columns_fails(self):
        triples = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        test-data:sub test-data:pred test-data:obj , test-data:object .
        """
        state = Graph()
        state.parse(data=triples, format="ttl")

        select_query = """
        select ?s ?p ?o { ?s ?p ?o }
        """
        spec_graph = Graph()
        spec = """
        @prefix sh: <http://www.w3.org/ns/shacl#> .
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .

        test-data:my_failing_spec
            a must:TestSpec ;
            must:then  [ a must:TableDataset ;
                        must:hasRow [ must:hasBinding[
                                       must:variable "s" ;
                                       must:boundValue test-data:subject ; 
                                        ] , [
                                       must:variable "o" ;
                                       must:boundValue test-data:obj  ; 
                                        ]; ] ;
                         ].
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_spec

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              folder_location=None,
                                              mustrd_triple_store=self.triple_store)

        spec_result = run_select_spec(spec_uri, state, select_query, then_component.value, self.triple_store)

        print(spec_result)
        if type(spec_result) == SelectSpecFailure:
            table_diff = spec_result.table_comparison.to_markdown()
            message = spec_result.message
            assert type(then_component) == TableThenSpec
            assert spec_result.spec_uri == spec_uri
            assert message == "Expected 1 row(s) and 2 column(s), got 2 row(s) and 3 column(s)"
            assert table_diff == """|    | ('s', 'expected')                              | ('s', 'actual')                            | ('s_datatype', 'expected')              | ('s_datatype', 'actual')                | ('o', 'expected')                          | ('o', 'actual')                               | ('o_datatype', 'expected')              | ('o_datatype', 'actual')                | ('p', 'expected')   | ('p', 'actual')                             | ('p_datatype', 'expected')   | ('p_datatype', 'actual')                |
|---:|:-----------------------------------------------|:-------------------------------------------|:----------------------------------------|:----------------------------------------|:-------------------------------------------|:----------------------------------------------|:----------------------------------------|:----------------------------------------|:--------------------|:--------------------------------------------|:-----------------------------|:----------------------------------------|
|  0 |                                                | https://semanticpartners.com/data/test/sub |                                         | http://www.w3.org/2001/XMLSchema#anyURI |                                            | https://semanticpartners.com/data/test/obj    |                                         | http://www.w3.org/2001/XMLSchema#anyURI |                     | https://semanticpartners.com/data/test/pred |                              | http://www.w3.org/2001/XMLSchema#anyURI |
|  1 |                                                | https://semanticpartners.com/data/test/sub |                                         | http://www.w3.org/2001/XMLSchema#anyURI |                                            | https://semanticpartners.com/data/test/object |                                         | http://www.w3.org/2001/XMLSchema#anyURI |                     | https://semanticpartners.com/data/test/pred |                              | http://www.w3.org/2001/XMLSchema#anyURI |
|  2 | https://semanticpartners.com/data/test/subject |                                            | http://www.w3.org/2001/XMLSchema#anyURI |                                         | https://semanticpartners.com/data/test/obj |                                               | http://www.w3.org/2001/XMLSchema#anyURI |                                         |                     |                                             |                              |                                         |"""
        else:
            raise Exception(f"wrong spec result type {spec_result}")

    def test_select_spec_ordered_passes(self):
        triples = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        test-data:sub1 test-data:pred1 test-data:obj1 .
        test-data:sub2 test-data:pred2 test-data:obj2 .
        """
        state = Graph()
        state.parse(data=triples, format="ttl")

        select_query = """
        select ?s ?p ?o { ?s ?p ?o } ORDER BY ?p
        """
        spec_graph = Graph()
        spec = """
        @prefix sh: <http://www.w3.org/ns/shacl#> .
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .

        test-data:my_first_spec 
            a must:TestSpec ;
            must:then  [ a must:TableDataset ;
                 must:hasRow [ sh:order 1 ;
                             must:hasBinding[ must:variable "s" ;
                                        must:boundValue  test-data:sub1 ; ],
                                      [ must:variable "p" ;
                                        must:boundValue  test-data:pred1 ; ],
                                      [ must:variable "o" ;
                                        must:boundValue  test-data:obj1 ; ] ; ] ,
                            [ sh:order 2 ;
                             must:hasBinding[ must:variable "s" ;
                                        must:boundValue  test-data:sub2 ; ],
                                      [ must:variable "p" ;
                                        must:boundValue  test-data:pred2 ; ],
                                      [ must:variable "o" ;
                                        must:boundValue  test-data:obj2 ; ] ; ] ; ] .
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_first_spec

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              folder_location=None,
                                              mustrd_triple_store=self.triple_store)

        spec_result = run_select_spec(spec_uri, state, select_query, then_component.value, self.triple_store,
                                      then_ordered=then_component.ordered)

        expected_result = SpecPassed(spec_uri, self.triple_store["type"])
        assert spec_result == expected_result
        assert type(then_component) == TableThenSpec

    def test_select_spec_ordered_passes_with_warning(self):
        triples = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        test-data:sub1 test-data:pred1 test-data:obj1 .
        test-data:sub2 test-data:pred2 test-data:obj2 .
        """
        state = Graph()
        state.parse(data=triples, format="ttl")

        select_query = """
        select ?s ?p ?o { ?s ?p ?o }
        """
        spec_graph = Graph()
        spec = """
        @prefix sh: <http://www.w3.org/ns/shacl#> .
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .

        test-data:my_first_spec 
            a must:TestSpec ;
            must:then  [ a must:TableDataset ;
                 must:hasRow [ sh:order 1 ;
                             must:hasBinding[ must:variable "s" ;
                                        must:boundValue  test-data:sub1 ; ],
                                      [ must:variable "p" ;
                                        must:boundValue  test-data:pred1 ; ],
                                      [ must:variable "o" ;
                                        must:boundValue  test-data:obj1 ; ] ; ] ,
                            [ sh:order 2 ;
                             must:hasBinding[ must:variable "s" ;
                                        must:boundValue  test-data:sub2 ; ],
                                      [ must:variable "p" ;
                                        must:boundValue  test-data:pred2 ; ],
                                      [ must:variable "o" ;
                                        must:boundValue  test-data:obj2 ; ] ; ] ; ] .
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_first_spec
        warning = f"sh:order in {spec_uri} is ignored, no ORDER BY in query"

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              folder_location=None,
                                              mustrd_triple_store=self.triple_store)

        spec_result = run_select_spec(spec_uri, state, select_query, then_component.value, self.triple_store,
                                      then_ordered=then_component.ordered)

        expected_result = SpecPassedWithWarning(spec_uri, self.triple_store["type"], warning)
        assert spec_result == expected_result
        assert type(then_component) == TableThenSpec

    def test_select_spec_ordered_fails(self):
        triples = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        test-data:sub1 test-data:pred1 test-data:obj1 .
        test-data:sub2 test-data:pred2 test-data:obj2 .
        """
        state = Graph()
        state.parse(data=triples, format="ttl")

        select_query = """
        select ?s ?p ?o { ?s ?p ?o } ORDER BY ?p
        """
        spec_graph = Graph()
        spec = """
        @prefix sh: <http://www.w3.org/ns/shacl#> .
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .

        test-data:my_failing_spec
            a must:TestSpec ;
            must:then  [ a must:TableDataset ;
                 must:hasRow [ sh:order 2 ;
                             must:hasBinding[ must:variable "s" ;
                                        must:boundValue  test-data:sub1 ; ],
                                      [ must:variable "p" ;
                                        must:boundValue  test-data:pred1 ; ],
                                      [ must:variable "o" ;
                                        must:boundValue  test-data:obj1 ; ] ; ] ,
                            [ sh:order 1 ;
                             must:hasBinding[ must:variable "s" ;
                                        must:boundValue  test-data:sub2 ; ],
                                      [ must:variable "p" ;
                                        must:boundValue  test-data:pred2 ; ],
                                      [ must:variable "o" ;
                                        must:boundValue  test-data:obj2 ; ] ; ] ; ] .
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_spec

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              folder_location=None,
                                              mustrd_triple_store=self.triple_store)

        spec_result = run_select_spec(spec_uri, state, select_query, then_component.value, self.triple_store,
                                      then_ordered=then_component.ordered)

        print(spec_result)
        if type(spec_result) == SelectSpecFailure:
            table_diff = spec_result.table_comparison.to_markdown()
            message = spec_result.message
            assert type(then_component) == TableThenSpec
            assert spec_result.spec_uri == spec_uri
            assert message == "Expected 2 row(s) and 3 column(s), got 2 row(s) and 3 column(s)"
            assert table_diff == """|    | ('s', 'expected')                           | ('s', 'actual')                             | ('p', 'expected')                            | ('p', 'actual')                              | ('o', 'expected')                           | ('o', 'actual')                             |
|---:|:--------------------------------------------|:--------------------------------------------|:---------------------------------------------|:---------------------------------------------|:--------------------------------------------|:--------------------------------------------|
|  0 | https://semanticpartners.com/data/test/sub2 | https://semanticpartners.com/data/test/sub1 | https://semanticpartners.com/data/test/pred2 | https://semanticpartners.com/data/test/pred1 | https://semanticpartners.com/data/test/obj2 | https://semanticpartners.com/data/test/obj1 |
|  1 | https://semanticpartners.com/data/test/sub1 | https://semanticpartners.com/data/test/sub2 | https://semanticpartners.com/data/test/pred1 | https://semanticpartners.com/data/test/pred2 | https://semanticpartners.com/data/test/obj1 | https://semanticpartners.com/data/test/obj2 |"""
        else:
            raise Exception(f"wrong spec result type {spec_result}")

    def test_select_spec_not_ordered_fails(self):
        triples = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        test-data:sub1 test-data:pred1 test-data:obj1 .
        test-data:sub2 test-data:pred2 test-data:obj2 .
        """
        state = Graph()
        state.parse(data=triples, format="ttl")

        select_query = """
        select ?s ?p ?o { ?s ?p ?o } ORDER BY ?p
        """
        spec_graph = Graph()
        spec = """
        @prefix sh: <http://www.w3.org/ns/shacl#> .
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .

        test-data:my_failing_spec
            a must:TestSpec ;
            must:then  [ a must:TableDataset ;
                 must:hasRow [ must:hasBinding[ must:variable "s" ;
                                        must:boundValue  test-data:sub1 ; ],
                                      [ must:variable "p" ;
                                        must:boundValue  test-data:pred1 ; ],
                                      [ must:variable "o" ;
                                        must:boundValue  test-data:obj1 ; ] ; ] ,
                            [ must:hasBinding[ must:variable "s" ;
                                        must:boundValue  test-data:sub2 ; ],
                                      [ must:variable "p" ;
                                        must:boundValue  test-data:pred2 ; ],
                                      [ must:variable "o" ;
                                        must:boundValue  test-data:obj2 ; ] ; ] ; ] .
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_spec

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              folder_location=None,
                                              mustrd_triple_store=self.triple_store)

        spec_result = run_select_spec(spec_uri, state, select_query, then_component.value, self.triple_store,
                                      then_component.ordered)

        print(spec_result)
        if type(spec_result) == SelectSpecFailure:
            table_diff = spec_result.table_comparison.to_markdown()
            message = spec_result.message
            assert type(then_component) == TableThenSpec
            assert spec_result.spec_uri == spec_uri
            assert message == "Expected 2 row(s) and 3 column(s), got 2 row(s) and 3 column(s). Actual result is ordered, must:then must contain sh:order on every row."
            assert table_diff == """|    | s                                           | s_datatype                              | p                                            | p_datatype                              | o                                           | o_datatype                              |
|---:|:--------------------------------------------|:----------------------------------------|:---------------------------------------------|:----------------------------------------|:--------------------------------------------|:----------------------------------------|
|  0 | https://semanticpartners.com/data/test/sub1 | http://www.w3.org/2001/XMLSchema#anyURI | https://semanticpartners.com/data/test/pred1 | http://www.w3.org/2001/XMLSchema#anyURI | https://semanticpartners.com/data/test/obj1 | http://www.w3.org/2001/XMLSchema#anyURI |
|  1 | https://semanticpartners.com/data/test/sub2 | http://www.w3.org/2001/XMLSchema#anyURI | https://semanticpartners.com/data/test/pred2 | http://www.w3.org/2001/XMLSchema#anyURI | https://semanticpartners.com/data/test/obj2 | http://www.w3.org/2001/XMLSchema#anyURI |"""
        else:
            raise Exception(f"wrong spec result type {spec_result}")

    def test_select_spec_not_all_ordered_fails(self):
        triples = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        test-data:sub1 test-data:pred1 test-data:obj1 .
        test-data:sub2 test-data:pred2 test-data:obj2 .
        """
        state = Graph()
        state.parse(data=triples, format="ttl")

        select_query = """
        select ?s ?p ?o { ?s ?p ?o } ORDER BY ?p
        """
        spec_graph = Graph()
        spec = """
        @prefix sh: <http://www.w3.org/ns/shacl#> .
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .

        test-data:my_failing_spec
            a must:TestSpec ;
            must:then  [ a must:TableDataset ;
                 must:hasRow [ must:hasBinding[ must:variable "s" ;
                                        must:boundValue  test-data:sub1 ; ],
                                      [ must:variable "p" ;
                                        must:boundValue  test-data:pred1 ; ],
                                      [ must:variable "o" ;
                                        must:boundValue  test-data:obj1 ; ] ; ] ,
                            [ sh:order 1 ;
                             must:hasBinding[ must:variable "s" ;
                                        must:boundValue  test-data:sub2 ; ],
                                      [ must:variable "p" ;
                                        must:boundValue  test-data:pred2 ; ],
                                      [ must:variable "o" ;
                                        must:boundValue  test-data:obj2 ; ] ; ] ; ] .
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_spec

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              folder_location=None,
                                              mustrd_triple_store=self.triple_store)

        spec_result = run_select_spec(spec_uri, state, select_query, then_component.value, self.triple_store,
                                      then_ordered=then_component.ordered)

        print(spec_result)
        if type(spec_result) == SelectSpecFailure:
            table_diff = spec_result.table_comparison.to_markdown()
            message = spec_result.message
            assert type(then_component) == TableThenSpec
            assert spec_result.spec_uri == spec_uri
            assert message == "Expected 2 row(s) and 3 column(s), got 2 row(s) and 3 column(s). Actual result is ordered, must:then must contain sh:order on every row."
            assert table_diff == """|    | s                                           | s_datatype                              | p                                            | p_datatype                              | o                                           | o_datatype                              |
|---:|:--------------------------------------------|:----------------------------------------|:---------------------------------------------|:----------------------------------------|:--------------------------------------------|:----------------------------------------|
|  0 | https://semanticpartners.com/data/test/sub1 | http://www.w3.org/2001/XMLSchema#anyURI | https://semanticpartners.com/data/test/pred1 | http://www.w3.org/2001/XMLSchema#anyURI | https://semanticpartners.com/data/test/obj1 | http://www.w3.org/2001/XMLSchema#anyURI |
|  1 | https://semanticpartners.com/data/test/sub2 | http://www.w3.org/2001/XMLSchema#anyURI | https://semanticpartners.com/data/test/pred2 | http://www.w3.org/2001/XMLSchema#anyURI | https://semanticpartners.com/data/test/obj2 | http://www.w3.org/2001/XMLSchema#anyURI |"""
        else:
            raise Exception(f"wrong spec result type {spec_result}")

    def test_select_spec_expected_fewer_rows_fails(self):
        triples = """
            @prefix test-data: <https://semanticpartners.com/data/test/> .
            test-data:sub test-data:pred test-data:obj .
            test-data:subject test-data:predicate test-data:object .
            """
        state = Graph()
        state.parse(data=triples, format="ttl")

        select_query = """
            select ?s ?p ?o { ?s ?p ?o } order by ?p
            """
        spec_graph = Graph()
        spec = """
            @prefix sh: <http://www.w3.org/ns/shacl#> .
            @prefix must: <https://mustrd.com/model/> .
            @prefix test-data: <https://semanticpartners.com/data/test/> .

            test-data:my_failing_spec
                    a must:TestSpec ;
                    must:then  [ a must:TableDataset ;
                            must:hasRow [ must:hasBinding[
                                           must:variable "s" ;
                                           must:boundValue test-data:sub ; 
                                            ] ,
                                            [
                                           must:variable "p" ;
                                           must:boundValue test-data:pred ; 
                                            ] ,
                                            [
                                           must:variable "o" ;
                                           must:boundValue test-data:obj  ; 
                                            ]; ] ;
                             ].
            """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_spec

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              folder_location=None,
                                              mustrd_triple_store=self.triple_store)

        spec_result = run_select_spec(spec_uri, state, select_query, then_component.value, self.triple_store,
                                      then_ordered=then_component.ordered)

        print(spec_result)
        if type(spec_result) == SelectSpecFailure:
            table_diff = spec_result.table_comparison.to_markdown()
            message = spec_result.message
            assert type(then_component) == TableThenSpec
            assert spec_result.spec_uri == spec_uri
            assert message == "Expected 1 row(s) and 3 column(s), got 2 row(s) and 3 column(s). Actual result is ordered, must:then must contain sh:order on every row."
            assert table_diff == """|    | ('s', 'expected')   | ('s', 'actual')                                | ('s_datatype', 'expected')   | ('s_datatype', 'actual')                | ('p', 'expected')   | ('p', 'actual')                                  | ('p_datatype', 'expected')   | ('p_datatype', 'actual')                | ('o', 'expected')   | ('o', 'actual')                               | ('o_datatype', 'expected')   | ('o_datatype', 'actual')                |
|---:|:--------------------|:-----------------------------------------------|:-----------------------------|:----------------------------------------|:--------------------|:-------------------------------------------------|:-----------------------------|:----------------------------------------|:--------------------|:----------------------------------------------|:-----------------------------|:----------------------------------------|
|  0 |                     | https://semanticpartners.com/data/test/subject |                              | http://www.w3.org/2001/XMLSchema#anyURI |                     | https://semanticpartners.com/data/test/predicate |                              | http://www.w3.org/2001/XMLSchema#anyURI |                     | https://semanticpartners.com/data/test/object |                              | http://www.w3.org/2001/XMLSchema#anyURI |"""
        else:
            raise Exception(f"wrong spec result type {spec_result}")

    def test_select_given_file_then_file_spec_passes(self):
        project_root = get_project_root()
        given_path = "test/data/given.ttl"
        file_path = Path(os.path.join(project_root, given_path))
        triples = get_spec_component_from_file(file_path)
        state = Graph()
        state.parse(data=triples, format="ttl")

        select_query = """
        select ?s ?p ?o { ?s ?p ?o }
        """
        spec_graph = Graph()
        spec = """
        @prefix sh: <http://www.w3.org/ns/shacl#> .
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .

        test-data:my_first_spec 
            a must:TestSpec ;
            must:then  [ a must:FileDataset ;
                                   must:file "test/data/thenSuccess.csv" ] .
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_first_spec

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              folder_location=None,
                                              mustrd_triple_store=self.triple_store)

        spec_result = run_select_spec(spec_uri, state, select_query, then_component.value, self.triple_store)

        expected_result = SpecPassed(spec_uri, self.triple_store["type"])
        assert spec_result == expected_result
        assert type(then_component) == TableThenSpec

    def test_select_given_file_then_file_spec_fails(self):
        project_root = get_project_root()
        given_path = "test/data/given.ttl"
        file_path = Path(os.path.join(project_root, given_path))
        triples = get_spec_component_from_file(file_path)
        state = Graph()
        state.parse(data=triples, format="ttl")

        select_query = """
        select ?s ?p ?o { ?s ?p ?o }
        """
        spec_graph = Graph()
        spec = """
        @prefix sh: <http://www.w3.org/ns/shacl#> .
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .

        test-data:my_first_spec 
            a must:TestSpec ;
            must:then  [ a must:FileDataset ;
                                   must:file "test/data/thenFail.csv" ] .
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_first_spec

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              folder_location=None,
                                              mustrd_triple_store=self.triple_store)

        spec_result = run_select_spec(spec_uri, state, select_query, then_component.value, self.triple_store)

        if type(spec_result) == SelectSpecFailure:
            table_diff = spec_result.table_comparison.to_markdown()
            message = spec_result.message
            assert type(then_component) == TableThenSpec
            assert spec_result.spec_uri == spec_uri
            assert message == "Expected 1 row(s) and 3 column(s), got 1 row(s) and 3 column(s)"
            assert table_diff == """|    | ('o', 'expected')                           | ('o', 'actual')                            |
|---:|:--------------------------------------------|:-------------------------------------------|
|  0 | https://semanticpartners.com/data/test/obj2 | https://semanticpartners.com/data/test/obj |"""
        else:
            raise Exception(f"wrong spec result type {spec_result}")
