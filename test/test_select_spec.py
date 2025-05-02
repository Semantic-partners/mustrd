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


from pyparsing import ParseException
from rdflib import Graph
from rdflib.namespace import Namespace

from pathlib import Path

from mustrd.mustrd import run_when, SpecPassed, SelectSpecFailure, SparqlParseFailure, \
    SpecPassedWithWarning, check_result, Specification
from mustrd.namespace import MUST, TRIPLESTORE
from mustrd.spec_component import get_spec_component_from_file, TableThenSpec, parse_spec_component
from test.addspec_source_file_to_spec_graph import addspec_source_file_to_spec_graph, parse_spec

TEST_DATA = Namespace("https://semanticpartners.com/data/test/")


class TestRunSelectSpec:
    given_sub_pred_obj = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        test-data:sub test-data:pred test-data:obj .
        """

    triple_store = {"type": TRIPLESTORE.RdfLib}

    def test_select_spec_passes(self):

        given = Graph().parse(data=self.given_sub_pred_obj, format="ttl")
        spec = """
        @prefix sh: <http://www.w3.org/ns/shacl#> .
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .

        test-data:my_first_spec
            a must:TestSpec ;
            must:when  [ a must:TextSparqlSource ;
                                   must:queryText  "select ?s ?p ?o { ?s ?p ?o }" ;
                                   must:queryType must:SelectSparql ] ;
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
        spec_graph = Graph().parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_first_spec
        addspec_source_file_to_spec_graph(spec_graph, spec_uri, __name__)

        when_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.when,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)
        self.triple_store["given"] = given
        spec = Specification(spec_uri, self.triple_store, given, when_component, then_component)
        when_result = run_when(spec_uri, self.triple_store, when_component[0])
        then_result = check_result(spec, when_result)

        expected_result = SpecPassed(spec_uri, self.triple_store["type"])
        assert then_result == expected_result
        assert isinstance(then_component, TableThenSpec)

    def test_select_spec_fails_with_expected_vs_actual_table_comparison(self):

        given = Graph().parse(data=self.given_sub_pred_obj, format="ttl")
        spec = """
        @prefix sh: <http://www.w3.org/ns/shacl#> .
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .

        test-data:my_failing_spec
            a must:TestSpec ;
            must:when  [ a must:TextSparqlSource ;
                       must:queryText  "select ?s ?p ?o { ?s ?p ?o }" ;
                       must:queryType must:SelectSparql ] ;
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
        spec_graph = Graph().parse(data=spec, format='ttl')
        spec_uri = TEST_DATA.my_failing_spec
        addspec_source_file_to_spec_graph(spec_graph, spec_uri, __name__)

        when_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.when,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)
        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        self.triple_store["given"] = given
        spec = Specification(spec_uri, self.triple_store, given, when_component, then_component)
        when_result = run_when(spec_uri, self.triple_store, when_component[0])
        then_result = check_result(spec, when_result)

        if isinstance(then_result, SelectSpecFailure):
            table_diff = then_result.table_comparison.to_markdown()
            assert isinstance(then_component, TableThenSpec)
            assert then_result.spec_uri == spec_uri
            assert table_diff == \
                """|    | ('s', 'expected')                                    | ('s', 'actual')                            |
|---:|:-----------------------------------------------------|:-------------------------------------------|
|  0 | https://semanticpartners.com/data/test/wrong-subject | https://semanticpartners.com/data/test/sub |""" # noqa
        else:
            raise Exception(f"wrong spec result type {then_result}")

    def test_select_spec_fails_for_different_types(self):

        triples = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
        test-data:sub test-data:pred "1"^^xsd:integer .
        """

        given = Graph().parse(data=triples, format="ttl")
        spec = """
        @prefix sh: <http://www.w3.org/ns/shacl#> .
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .

        test-data:my_failing_spec
            a must:TestSpec ;
                        must:when  [ a must:TextSparqlSource ;
                       must:queryText  "select ?s ?p ?o { ?s ?p ?o }" ;
                       must:queryType must:SelectSparql ] ;
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
        spec_graph = Graph().parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_spec

        addspec_source_file_to_spec_graph(spec_graph, spec_uri, __name__)

        when_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.when,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)
        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        self.triple_store["given"] = given
        spec = Specification(spec_uri, self.triple_store, given, when_component, then_component)
        when_result = run_when(spec_uri, self.triple_store, when_component[0])
        then_result = check_result(spec, when_result)
        if isinstance(then_result, SelectSpecFailure):
            table_diff = then_result.table_comparison.to_markdown()
            assert isinstance(then_component, TableThenSpec)
            assert then_result.spec_uri == spec_uri
            assert table_diff == """|    |   ('o', 'expected') |   ('o', 'actual') | ('o_datatype', 'expected')               | ('o_datatype', 'actual')                 |
|---:|--------------------:|------------------:|:-----------------------------------------|:-----------------------------------------|
|  0 |                   1 |                 1 | http://www.w3.org/2001/XMLSchema#decimal | http://www.w3.org/2001/XMLSchema#integer |""" # noqa
        else:
            raise Exception(f"wrong spec result type {then_result}")

    def test_select_spec_fails_for_different_types_where_one_is_string(self):

        triples = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        test-data:sub test-data:pred 1 .
        """

        given = Graph().parse(data=triples, format="ttl")

        spec = """
        @prefix sh: <http://www.w3.org/ns/shacl#> .
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .

        test-data:my_failing_spec
            a must:TestSpec ;
            must:when  [ a must:TextSparqlSource ;
                    must:queryText  "select ?s ?p ?o { ?s ?p ?o }" ;
                    must:queryType must:SelectSparql ] ;
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
        spec_graph = Graph().parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_spec

        addspec_source_file_to_spec_graph(spec_graph, spec_uri, __name__)

        when_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.when,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        self.triple_store["given"] = given
        spec = Specification(spec_uri, self.triple_store, given, when_component, then_component)
        when_result = run_when(spec_uri, self.triple_store, when_component[0])
        then_result = check_result(spec, when_result)

        if isinstance(then_result, SelectSpecFailure):
            table_diff = then_result.table_comparison.to_markdown()
            assert isinstance(then_component, TableThenSpec)
            assert then_result.spec_uri == spec_uri
            assert table_diff == \
                """|    | ('o_datatype', 'expected')              | ('o_datatype', 'actual')                 |
|---:|:----------------------------------------|:-----------------------------------------|
|  0 | http://www.w3.org/2001/XMLSchema#string | http://www.w3.org/2001/XMLSchema#integer |"""
        else:
            raise Exception(f"wrong spec result type {then_result}")

    def test_invalid_select_statement_spec_fails(self):

        triples = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        test-data:sub test-data:pred 1 .
        """

        given = Graph().parse(data=triples, format="ttl")

        spec = """
            @prefix sh: <http://www.w3.org/ns/shacl#> .
            @prefix must: <https://mustrd.com/model/> .
            @prefix test-data: <https://semanticpartners.com/data/test/> .

            test-data:my_failing_spec
                a must:TestSpec ;
                must:when  [ a must:TextSparqlSource ;
                        must:queryText  "select ?s ?p ?o { typo }" ;
                        must:queryType must:SelectSparql ] ;
                must:then  [ a must:TableDataset ;
                            must:hasRow [ must:hasBinding[
                                           must:variable "s" ;
                                           must:boundValue test-data:wrong-subject ;
                                            ] ; ] ;
                    ].
            """
        spec_graph = Graph().parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_spec

        addspec_source_file_to_spec_graph(spec_graph, spec_uri, __name__)

        when_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.when,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        self.triple_store["given"] = given
        try:
            when_result = run_when(spec_uri, self.triple_store, when_component[0])
        except ParseException as e:
            when_result = SparqlParseFailure(spec_uri, self.triple_store["type"], e)

        if isinstance(when_result, SparqlParseFailure):
            assert isinstance(then_component, TableThenSpec)
            assert when_result.spec_uri == spec_uri
            assert str(
                when_result.exception) == "Expected SelectQuery, found 'typo'  (at char 18), (line:1, col:19)"
        else:
            raise Exception(f"wrong spec result type {when_result}")

    def test_select_with_variables_spec_passes(self):

        triples = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        test-data:sub test-data:pred "hello world" .
        """
        given = Graph().parse(data=triples, format="ttl")
        spec = """
        @prefix sh: <http://www.w3.org/ns/shacl#> .
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .

        test-data:my_first_spec
            a must:TestSpec ;
            must:when  [ a must:TextSparqlSource ;
                        must:queryText  "select ?s ?p ?o { ?s ?p ?o }" ;
                        must:queryType must:SelectSparql ;
                        must:hasBinding [ must:variable "o" ;
                                 must:boundValue  "hello world" ; ] ;] ;
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
        spec_graph = Graph().parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_first_spec

        addspec_source_file_to_spec_graph(spec_graph, spec_uri, __name__)

        when_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.when,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        self.triple_store["given"] = given
        spec = Specification(spec_uri, self.triple_store, given, when_component, then_component)
        when_result = run_when(spec_uri, self.triple_store, when_component[0])
        then_result = check_result(spec, when_result)

        expected_result = SpecPassed(spec_uri, self.triple_store["type"])
        assert then_result == expected_result
        assert isinstance(then_component, TableThenSpec)

    def test_select_with_variables_spec_fails_with_expected_vs_actual_table_comparison(self):

        triples = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        test-data:sub test-data:pred "hello world" .
        """
        given = Graph().parse(data=triples, format="ttl")
        spec = """
        @prefix sh: <http://www.w3.org/ns/shacl#> .
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .

        test-data:my_first_spec
            a must:TestSpec ;
            must:when  [ a must:TextSparqlSource ;
                        must:queryText  "select ?s ?p ?o { ?s ?p ?o }" ;
                        must:queryType must:SelectSparql ;
                        must:hasBinding [ must:variable "o" ;
                                 must:boundValue  "hello world" ; ] ;] ;
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
        spec_graph = Graph().parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_first_spec

        addspec_source_file_to_spec_graph(spec_graph, spec_uri, __name__)

        when_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.when,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        self.triple_store["given"] = given
        spec = Specification(spec_uri, self.triple_store, given, when_component, then_component)
        when_result = run_when(spec_uri, self.triple_store, when_component[0])
        then_result = check_result(spec, when_result)

        if isinstance(then_result, SelectSpecFailure):
            table_diff = then_result.table_comparison.to_markdown()
            assert isinstance(then_component, TableThenSpec)
            assert then_result.spec_uri == spec_uri
            assert table_diff == """|    | ('o', 'expected')   | ('o', 'actual')   |
|---:|:--------------------|:------------------|
|  0 | hello worlds        | hello world       |"""
        else:
            raise Exception(f"wrong spec result type {then_result}")

    def test_select_spec_expect_empty_result_passes(self):

        given = Graph().parse(data=self.given_sub_pred_obj, format="ttl")

        spec = """
        @prefix sh: <http://www.w3.org/ns/shacl#> .
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .

        test-data:my_first_spec
            a must:TestSpec ;
            must:when  [ a must:TextSparqlSource ;
                    must:queryText  "select ?a ?b ?c { ?s ?p ?o }" ;
                    must:queryType must:SelectSparql ] ;
            must:then  [ a must:EmptyTable ] .
        """
        spec_graph = Graph().parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_first_spec

        addspec_source_file_to_spec_graph(spec_graph, spec_uri, __name__)

        when_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.when,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        self.triple_store["given"] = given
        spec = Specification(spec_uri, self.triple_store, given, when_component, then_component)
        when_result = run_when(spec_uri, self.triple_store, when_component[0])
        then_result = check_result(spec, when_result)

        expected_result = SpecPassed(spec_uri, self.triple_store["type"])
        assert isinstance(then_component, TableThenSpec)
        assert then_result == expected_result

    def test_select_spec_expect_empty_result_fails(self):

        given = Graph().parse(data=self.given_sub_pred_obj, format="ttl")

        spec = """
            @prefix sh: <http://www.w3.org/ns/shacl#> .
            @prefix must: <https://mustrd.com/model/> .
            @prefix test-data: <https://semanticpartners.com/data/test/> .

            test-data:my_failing_spec
                a must:TestSpec ;
                must:when  [ a must:TextSparqlSource ;
                        must:queryText  "select ?s ?p ?o { ?s ?p ?o }" ;
                        must:queryType must:SelectSparql ] ;
                        must:then  [ a must:EmptyTable ] .
                    """

        spec_graph = Graph().parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_spec
        when_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.when,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        self.triple_store["given"] = given
        spec = Specification(spec_uri, self.triple_store, given, when_component, then_component)
        when_result = run_when(spec_uri, self.triple_store, when_component[0])
        then_result = check_result(spec, when_result)

        if isinstance(then_result, SelectSpecFailure):
            table_diff = then_result.table_comparison.to_markdown()
            assert isinstance(then_component, TableThenSpec)
            assert then_result.spec_uri == spec_uri
            assert table_diff == """|    | ('s', 'expected')   | ('s', 'actual')                            | ('s_datatype', 'expected')   | ('s_datatype', 'actual')                | ('p', 'expected')   | ('p', 'actual')                             | ('p_datatype', 'expected')   | ('p_datatype', 'actual')                | ('o', 'expected')   | ('o', 'actual')                            | ('o_datatype', 'expected')   | ('o_datatype', 'actual')                |
|---:|:--------------------|:-------------------------------------------|:-----------------------------|:----------------------------------------|:--------------------|:--------------------------------------------|:-----------------------------|:----------------------------------------|:--------------------|:-------------------------------------------|:-----------------------------|:----------------------------------------|
|  0 |                     | https://semanticpartners.com/data/test/sub |                              | http://www.w3.org/2001/XMLSchema#anyURI |                     | https://semanticpartners.com/data/test/pred |                              | http://www.w3.org/2001/XMLSchema#anyURI |                     | https://semanticpartners.com/data/test/obj |                              | http://www.w3.org/2001/XMLSchema#anyURI |""" # noqa
        else:
            raise Exception(f"wrong spec result type {then_result}")

    def test_select_spec_unexpected_empty_result_fails(self):
        given = Graph().parse(data=self.given_sub_pred_obj, format="ttl")

        spec = """
            @prefix sh: <http://www.w3.org/ns/shacl#> .
            @prefix must: <https://mustrd.com/model/> .
            @prefix test-data: <https://semanticpartners.com/data/test/> .

            test-data:my_failing_spec
                a must:TestSpec ;
                must:when  [ a must:TextSparqlSource ;
                        must:queryText  "select ?a ?b ?c { ?s ?p ?o }" ;
                        must:queryType must:SelectSparql ] ;
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
        spec_graph = Graph().parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_spec
        when_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.when,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        self.triple_store["given"] = given
        spec = Specification(spec_uri, self.triple_store, given, when_component, then_component)
        when_result = run_when(spec_uri, self.triple_store, when_component[0])
        then_result = check_result(spec, when_result)

        if isinstance(then_result, SelectSpecFailure):
            table_diff = then_result.table_comparison.to_markdown()
            assert isinstance(then_component, TableThenSpec)
            assert then_result.spec_uri == spec_uri
            assert table_diff == """|    | ('o', 'expected')                          | ('o', 'actual')   | ('o_datatype', 'expected')              | ('o_datatype', 'actual')   | ('p', 'expected')                           | ('p', 'actual')   | ('p_datatype', 'expected')              | ('p_datatype', 'actual')   | ('s', 'expected')                          | ('s', 'actual')   | ('s_datatype', 'expected')              | ('s_datatype', 'actual')   |
|---:|:-------------------------------------------|:------------------|:----------------------------------------|:---------------------------|:--------------------------------------------|:------------------|:----------------------------------------|:---------------------------|:-------------------------------------------|:------------------|:----------------------------------------|:---------------------------|
|  0 | https://semanticpartners.com/data/test/obj |                   | http://www.w3.org/2001/XMLSchema#anyURI |                            | https://semanticpartners.com/data/test/pred |                   | http://www.w3.org/2001/XMLSchema#anyURI |                            | https://semanticpartners.com/data/test/sub |                   | http://www.w3.org/2001/XMLSchema#anyURI |                            |""" # noqa
        else:
            raise Exception(f"wrong spec result type {then_result}")

    def test_select_with_different_types_of_variables_spec_passes(self):
        triples = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        test-data:sub test-data:pred true .
        """
        given = Graph().parse(data=triples, format="ttl")

        spec = """
            @prefix sh: <http://www.w3.org/ns/shacl#> .
            @prefix must: <https://mustrd.com/model/> .
            @prefix test-data: <https://semanticpartners.com/data/test/> .

            test-data:my_failing_spec
                a must:TestSpec ;
                must:when  [ a must:TextSparqlSource ;
                        must:queryText  "select ?s ?p ?o { ?s ?p ?o }" ;
                        must:queryType must:SelectSparql ;
                        must:hasBinding [ must:variable "o" ;
                                        must:boundValue  true ; ] ;] ;
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
        spec_graph = Graph().parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_spec
        when_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.when,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        self.triple_store["given"] = given
        spec = Specification(spec_uri, self.triple_store, given, when_component, then_component)
        when_result = run_when(spec_uri, self.triple_store, when_component[0])
        then_result = check_result(spec, when_result)

        expected_result = SpecPassed(spec_uri, self.triple_store["type"])
        assert then_result == expected_result
        assert isinstance(then_component, TableThenSpec)

    def test_select_spec_different_types_of_variables_spec_fails(self):
        triples = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        test-data:sub test-data:pred test-data:obj , 25 .
        """
        given = Graph().parse(data=triples, format="ttl")

        spec = """
            @prefix sh: <http://www.w3.org/ns/shacl#> .
            @prefix must: <https://mustrd.com/model/> .
            @prefix test-data: <https://semanticpartners.com/data/test/> .

            test-data:my_failing_spec
                a must:TestSpec ;
                must:when  [ a must:TextSparqlSource ;
                        must:queryText  "select ?o { ?s ?p ?o }" ;
                        must:queryType must:SelectSparql ;
                        must:hasBinding [ must:variable "o" ;
                                            must:boundValue  25 ; ] ;] ;
            must:then  [ a must:TableDataset ;
                        must:hasRow [ must:hasBinding
                                        [
                                       must:variable "o" ;
                                       must:boundValue 25.0  ;
                                        ]; ] ;
                         ].
        """
        spec_graph = Graph().parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_spec
        when_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.when,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        self.triple_store["given"] = given
        spec = Specification(spec_uri, self.triple_store, given, when_component, then_component)
        when_result = run_when(spec_uri, self.triple_store, when_component[0])
        then_result = check_result(spec, when_result)

        if isinstance(then_result, SelectSpecFailure):
            table_diff = then_result.table_comparison.to_markdown()
            assert isinstance(then_component, TableThenSpec)
            assert then_result.spec_uri == spec_uri
            assert table_diff == """|    |   ('o', 'expected') |   ('o', 'actual') | ('o_datatype', 'expected')               | ('o_datatype', 'actual')                 |
|---:|--------------------:|------------------:|:-----------------------------------------|:-----------------------------------------|
|  0 |                  25 |                25 | http://www.w3.org/2001/XMLSchema#decimal | http://www.w3.org/2001/XMLSchema#integer |""" # noqa
        else:
            raise Exception(f"wrong spec result type {then_result}")

    def test_select_spec_multiline_then_passes(self):

        triples = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        test-data:sub test-data:pred test-data:obj , test-data:object .
        """
        given = Graph().parse(data=triples, format="ttl")

        spec = """
            @prefix sh: <http://www.w3.org/ns/shacl#> .
            @prefix must: <https://mustrd.com/model/> .
            @prefix test-data: <https://semanticpartners.com/data/test/> .

            test-data:my_first_spec
                a must:TestSpec ;
                must:when  [ a must:TextSparqlSource ;
                        must:queryText  "select ?s ?p ?o { ?s ?p ?o }" ;
                        must:queryType must:SelectSparql ] ;
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
        spec_graph = Graph().parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_first_spec
        when_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.when,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        self.triple_store["given"] = given
        spec = Specification(spec_uri, self.triple_store, given, when_component, then_component)
        when_result = run_when(spec_uri, self.triple_store, when_component[0])
        then_result = check_result(spec, when_result)

        expected_result = SpecPassed(spec_uri, self.triple_store["type"])
        assert then_result == expected_result
        assert isinstance(then_component, TableThenSpec)

    def test_select_spec_expected_fewer_columns_fails(self):
        given = Graph().parse(data=self.given_sub_pred_obj, format="ttl")

        spec = """
            @prefix sh: <http://www.w3.org/ns/shacl#> .
            @prefix must: <https://mustrd.com/model/> .
            @prefix test-data: <https://semanticpartners.com/data/test/> .

            test-data:my_failing_spec
                a must:TestSpec ;
                must:when  [ a must:TextSparqlSource ;
                        must:queryText  "select ?s ?p ?o { ?s ?p ?o }" ;
                        must:queryType must:SelectSparql ] ;
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
        spec_graph = Graph().parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_spec
        when_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.when,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        self.triple_store["given"] = given
        spec = Specification(spec_uri, self.triple_store, given, when_component, then_component)
        when_result = run_when(spec_uri, self.triple_store, when_component[0])
        then_result = check_result(spec, when_result)
        if isinstance(then_result, SelectSpecFailure):
            table_diff = then_result.table_comparison.to_markdown()
            message = then_result.message
            assert isinstance(then_component, TableThenSpec)
            assert then_result.spec_uri == spec_uri
            assert message == "Expected 1 row(s) and 2 column(s), got 1 row(s) and 3 column(s)"
            assert table_diff == """|    | ('o', 'expected')                          | ('o', 'actual')                            | ('o_datatype', 'expected')              | ('o_datatype', 'actual')                | ('s', 'expected')                          | ('s', 'actual')                            | ('s_datatype', 'expected')              | ('s_datatype', 'actual')                | ('p', 'expected')   | ('p', 'actual')                             | ('p_datatype', 'expected')   | ('p_datatype', 'actual')                |
|---:|:-------------------------------------------|:-------------------------------------------|:----------------------------------------|:----------------------------------------|:-------------------------------------------|:-------------------------------------------|:----------------------------------------|:----------------------------------------|:--------------------|:--------------------------------------------|:-----------------------------|:----------------------------------------|
|  0 | https://semanticpartners.com/data/test/obj | https://semanticpartners.com/data/test/obj | http://www.w3.org/2001/XMLSchema#anyURI | http://www.w3.org/2001/XMLSchema#anyURI | https://semanticpartners.com/data/test/sub | https://semanticpartners.com/data/test/sub | http://www.w3.org/2001/XMLSchema#anyURI | http://www.w3.org/2001/XMLSchema#anyURI |                     | https://semanticpartners.com/data/test/pred |                              | http://www.w3.org/2001/XMLSchema#anyURI |""" # noqa
        else:
            raise Exception(f"wrong spec result type {then_result}")

    def test_select_spec_expected_more_columns_fails(self):
        given = Graph().parse(data=self.given_sub_pred_obj, format="ttl")

        spec = """
            @prefix sh: <http://www.w3.org/ns/shacl#> .
            @prefix must: <https://mustrd.com/model/> .
            @prefix test-data: <https://semanticpartners.com/data/test/> .

            test-data:my_failing_spec
                a must:TestSpec ;
                must:when  [ a must:TextSparqlSource ;
                        must:queryText  "select ?s ?p { ?s ?p ?o }" ;
                        must:queryType must:SelectSparql ] ;
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
        spec_graph = Graph().parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_spec
        when_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.when,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        self.triple_store["given"] = given
        spec = Specification(spec_uri, self.triple_store, given, when_component, then_component)
        when_result = run_when(spec_uri, self.triple_store, when_component[0])
        then_result = check_result(spec, when_result)
        if isinstance(then_result, SelectSpecFailure):
            table_diff = then_result.table_comparison.to_markdown()
            message = then_result.message
            assert isinstance(then_component, TableThenSpec)
            assert then_result.spec_uri == spec_uri
            assert message == "Expected 1 row(s) and 3 column(s), got 1 row(s) and 2 column(s)"
            assert table_diff == """|    | ('o', 'expected')                          | ('o', 'actual')   | ('o_datatype', 'expected')              | ('o_datatype', 'actual')   | ('p', 'expected')                           | ('p', 'actual')                             | ('p_datatype', 'expected')              | ('p_datatype', 'actual')                | ('s', 'expected')                          | ('s', 'actual')                            | ('s_datatype', 'expected')              | ('s_datatype', 'actual')                |
|---:|:-------------------------------------------|:------------------|:----------------------------------------|:---------------------------|:--------------------------------------------|:--------------------------------------------|:----------------------------------------|:----------------------------------------|:-------------------------------------------|:-------------------------------------------|:----------------------------------------|:----------------------------------------|
|  0 | https://semanticpartners.com/data/test/obj |                   | http://www.w3.org/2001/XMLSchema#anyURI |                            | https://semanticpartners.com/data/test/pred | https://semanticpartners.com/data/test/pred | http://www.w3.org/2001/XMLSchema#anyURI | http://www.w3.org/2001/XMLSchema#anyURI | https://semanticpartners.com/data/test/sub | https://semanticpartners.com/data/test/sub | http://www.w3.org/2001/XMLSchema#anyURI | http://www.w3.org/2001/XMLSchema#anyURI |"""  # noqa
        else:
            raise Exception(f"wrong spec result type {then_result}")

    def test_select_spec_expected_fewer_and_different_columns_fails(self):
        given = Graph().parse(data=self.given_sub_pred_obj, format="ttl")

        spec = """
            @prefix sh: <http://www.w3.org/ns/shacl#> .
            @prefix must: <https://mustrd.com/model/> .
            @prefix test-data: <https://semanticpartners.com/data/test/> .

            test-data:my_failing_spec
                a must:TestSpec ;
                must:when  [ a must:TextSparqlSource ;
                        must:queryText  "select ?s ?p ?o { ?s ?p ?o }" ;
                        must:queryType must:SelectSparql ] ;
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
        spec_graph = Graph().parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_spec
        when_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.when,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        self.triple_store["given"] = given
        spec = Specification(spec_uri, self.triple_store, given, when_component, then_component)
        when_result = run_when(spec_uri, self.triple_store, when_component[0])
        then_result = check_result(spec, when_result)
        if isinstance(then_result, SelectSpecFailure):
            table_diff = then_result.table_comparison.to_markdown()
            message = then_result.message
            assert isinstance(then_component, TableThenSpec)
            assert then_result.spec_uri == spec_uri
            assert message == "Expected 1 row(s) and 2 column(s), got 1 row(s) and 3 column(s)"
            assert table_diff == """|    | ('obj', 'expected')                           | ('obj', 'actual')   | ('obj_datatype', 'expected')            | ('obj_datatype', 'actual')   | ('s', 'expected')                          | ('s', 'actual')                            | ('s_datatype', 'expected')              | ('s_datatype', 'actual')                | ('o', 'expected')   | ('o', 'actual')                            | ('o_datatype', 'expected')   | ('o_datatype', 'actual')                | ('p', 'expected')   | ('p', 'actual')                             | ('p_datatype', 'expected')   | ('p_datatype', 'actual')                |
|---:|:----------------------------------------------|:--------------------|:----------------------------------------|:-----------------------------|:-------------------------------------------|:-------------------------------------------|:----------------------------------------|:----------------------------------------|:--------------------|:-------------------------------------------|:-----------------------------|:----------------------------------------|:--------------------|:--------------------------------------------|:-----------------------------|:----------------------------------------|
|  0 | https://semanticpartners.com/data/test/object |                     | http://www.w3.org/2001/XMLSchema#anyURI |                              | https://semanticpartners.com/data/test/sub | https://semanticpartners.com/data/test/sub | http://www.w3.org/2001/XMLSchema#anyURI | http://www.w3.org/2001/XMLSchema#anyURI |                     | https://semanticpartners.com/data/test/obj |                              | http://www.w3.org/2001/XMLSchema#anyURI |                     | https://semanticpartners.com/data/test/pred |                              | http://www.w3.org/2001/XMLSchema#anyURI |""" # noqa
        else:
            raise Exception(f"wrong spec result type {then_result}")

    def test_select_spec_expected_fewer_rows_fails(self):
        triples = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        test-data:sub test-data:pred test-data:obj .
        test-data:subject test-data:predicate test-data:object .
        """
        given = Graph().parse(data=triples, format="ttl")

        spec = """
            @prefix sh: <http://www.w3.org/ns/shacl#> .
            @prefix must: <https://mustrd.com/model/> .
            @prefix test-data: <https://semanticpartners.com/data/test/> .

            test-data:my_failing_spec
                a must:TestSpec ;
                must:when  [ a must:TextSparqlSource ;
                        must:queryText  "select ?s ?p ?o { ?s ?p ?o }" ;
                        must:queryType must:SelectSparql ] ;
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
        spec_graph = Graph().parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_spec
        when_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.when,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        self.triple_store["given"] = given
        spec = Specification(spec_uri, self.triple_store, given, when_component, then_component)
        when_result = run_when(spec_uri, self.triple_store, when_component[0])
        then_result = check_result(spec, when_result)

        if isinstance(then_result, SelectSpecFailure):
            table_diff = then_result.table_comparison.to_markdown()
            message = then_result.message
            assert isinstance(then_component, TableThenSpec)
            assert then_result.spec_uri == spec_uri
            assert message == "Expected 1 row(s) and 3 column(s), got 2 row(s) and 3 column(s)"
            assert table_diff == """|    | ('s', 'expected')   | ('s', 'actual')                                | ('s_datatype', 'expected')   | ('s_datatype', 'actual')                | ('p', 'expected')   | ('p', 'actual')                                  | ('p_datatype', 'expected')   | ('p_datatype', 'actual')                | ('o', 'expected')   | ('o', 'actual')                               | ('o_datatype', 'expected')   | ('o_datatype', 'actual')                |
|---:|:--------------------|:-----------------------------------------------|:-----------------------------|:----------------------------------------|:--------------------|:-------------------------------------------------|:-----------------------------|:----------------------------------------|:--------------------|:----------------------------------------------|:-----------------------------|:----------------------------------------|
|  0 |                     | https://semanticpartners.com/data/test/subject |                              | http://www.w3.org/2001/XMLSchema#anyURI |                     | https://semanticpartners.com/data/test/predicate |                              | http://www.w3.org/2001/XMLSchema#anyURI |                     | https://semanticpartners.com/data/test/object |                              | http://www.w3.org/2001/XMLSchema#anyURI |""" # noqa
        else:
            raise Exception(f"wrong spec result type {then_result}")

    def test_select_spec_expected_more_rows_fails(self):
        given = Graph().parse(data=self.given_sub_pred_obj, format="ttl")

        spec = """
            @prefix sh: <http://www.w3.org/ns/shacl#> .
            @prefix must: <https://mustrd.com/model/> .
            @prefix test-data: <https://semanticpartners.com/data/test/> .

            test-data:my_failing_spec
                a must:TestSpec ;
                must:when  [ a must:TextSparqlSource ;
                        must:queryText  "select ?s ?p ?o { ?s ?p ?o }" ;
                        must:queryType must:SelectSparql ] ;
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
        spec_graph = Graph().parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_spec
        when_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.when,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        self.triple_store["given"] = given
        spec = Specification(spec_uri, self.triple_store, given, when_component, then_component)
        when_result = run_when(spec_uri, self.triple_store, when_component[0])
        then_result = check_result(spec, when_result)

        if isinstance(then_result, SelectSpecFailure):
            table_diff = then_result.table_comparison.to_markdown()
            message = then_result.message
            assert isinstance(then_component, TableThenSpec)
            assert then_result.spec_uri == spec_uri
            assert message == "Expected 2 row(s) and 3 column(s), got 1 row(s) and 3 column(s)"
            assert table_diff == """|    | ('s', 'expected')                              | ('s', 'actual')   | ('s_datatype', 'expected')              | ('s_datatype', 'actual')   | ('p', 'expected')                                | ('p', 'actual')   | ('p_datatype', 'expected')              | ('p_datatype', 'actual')   | ('o', 'expected')                             | ('o', 'actual')   | ('o_datatype', 'expected')              | ('o_datatype', 'actual')   |
|---:|:-----------------------------------------------|:------------------|:----------------------------------------|:---------------------------|:-------------------------------------------------|:------------------|:----------------------------------------|:---------------------------|:----------------------------------------------|:------------------|:----------------------------------------|:---------------------------|
|  0 | https://semanticpartners.com/data/test/subject |                   | http://www.w3.org/2001/XMLSchema#anyURI |                            | https://semanticpartners.com/data/test/predicate |                   | http://www.w3.org/2001/XMLSchema#anyURI |                            | https://semanticpartners.com/data/test/object |                   | http://www.w3.org/2001/XMLSchema#anyURI |                            |""" # noqa
        else:
            raise Exception(f"wrong spec result type {then_result}")

    def test_select_spec_expected_fewer_and_different_rows_fails(self):
        triples = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        test-data:sub1 test-data:pred1 test-data:obj1 .
        test-data:sub2 test-data:pred2 test-data:obj2 .
        test-data:sub3 test-data:pred3 test-data:obj3 .
        """
        given = Graph().parse(data=triples, format="ttl")

        spec = """
            @prefix sh: <http://www.w3.org/ns/shacl#> .
            @prefix must: <https://mustrd.com/model/> .
            @prefix test-data: <https://semanticpartners.com/data/test/> .

            test-data:my_failing_spec
                a must:TestSpec ;
                must:when  [ a must:TextSparqlSource ;
                        must:queryText  "select ?s ?p ?o { ?s ?p ?o }" ;
                        must:queryType must:SelectSparql ] ;
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
        spec_graph = Graph().parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_spec
        when_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.when,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        self.triple_store["given"] = given
        spec = Specification(spec_uri, self.triple_store, given, when_component, then_component)
        when_result = run_when(spec_uri, self.triple_store, when_component[0])
        then_result = check_result(spec, when_result)

        if isinstance(then_result, SelectSpecFailure):
            table_diff = then_result.table_comparison.to_markdown()
            message = then_result.message
            assert isinstance(then_component, TableThenSpec)
            assert then_result.spec_uri == spec_uri
            assert message == "Expected 2 row(s) and 3 column(s), got 3 row(s) and 3 column(s)"
            assert table_diff == """|    | ('s', 'expected')                           | ('s', 'actual')                             | ('s_datatype', 'expected')              | ('s_datatype', 'actual')                | ('p', 'expected')                            | ('p', 'actual')                              | ('p_datatype', 'expected')              | ('p_datatype', 'actual')                | ('o', 'expected')                           | ('o', 'actual')                             | ('o_datatype', 'expected')              | ('o_datatype', 'actual')                |
|---:|:--------------------------------------------|:--------------------------------------------|:----------------------------------------|:----------------------------------------|:---------------------------------------------|:---------------------------------------------|:----------------------------------------|:----------------------------------------|:--------------------------------------------|:--------------------------------------------|:----------------------------------------|:----------------------------------------|
|  0 |                                             | https://semanticpartners.com/data/test/sub2 |                                         | http://www.w3.org/2001/XMLSchema#anyURI |                                              | https://semanticpartners.com/data/test/pred2 |                                         | http://www.w3.org/2001/XMLSchema#anyURI |                                             | https://semanticpartners.com/data/test/obj2 |                                         | http://www.w3.org/2001/XMLSchema#anyURI |
|  1 |                                             | https://semanticpartners.com/data/test/sub3 |                                         | http://www.w3.org/2001/XMLSchema#anyURI |                                              | https://semanticpartners.com/data/test/pred3 |                                         | http://www.w3.org/2001/XMLSchema#anyURI |                                             | https://semanticpartners.com/data/test/obj3 |                                         | http://www.w3.org/2001/XMLSchema#anyURI |
|  2 | https://semanticpartners.com/data/test/sub4 |                                             | http://www.w3.org/2001/XMLSchema#anyURI |                                         | https://semanticpartners.com/data/test/pred4 |                                              | http://www.w3.org/2001/XMLSchema#anyURI |                                         | https://semanticpartners.com/data/test/obj4 |                                             | http://www.w3.org/2001/XMLSchema#anyURI |                                         |""" # noqa
        else:
            raise Exception(f"wrong spec result type {then_result}")

    def test_select_spec_with_optional_passes(self):
        triples = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        test-data:sub1 test-data:pred test-data:obj ; test-data:predicate test-data:object.
        test-data:sub2 test-data:pred test-data:obj .
        """
        given = Graph().parse(data=triples, format="ttl")
        spec = """
            @prefix sh: <http://www.w3.org/ns/shacl#> .
            @prefix must: <https://mustrd.com/model/> .
            @prefix test-data: <https://semanticpartners.com/data/test/> .

            test-data:my_first_spec
                a must:TestSpec ;
                must:when  [ a must:TextSparqlSource ;
                        must:queryText  "select ?s ?o ?object { ?s <https://semanticpartners.com/data/test/pred> ?o . OPTIONAL {?s <https://semanticpartners.com/data/test/predicate> ?object} }" ;
                        must:queryType must:SelectSparql ] ;
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
        """ # noqa
        spec_graph = Graph().parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_first_spec
        when_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.when,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        self.triple_store["given"] = given
        spec = Specification(spec_uri, self.triple_store, given, when_component, then_component)
        when_result = run_when(spec_uri, self.triple_store, when_component[0])
        then_result = check_result(spec, when_result)

        expected_result = SpecPassed(spec_uri, self.triple_store["type"])
        assert then_result == expected_result
        assert isinstance(then_component, TableThenSpec)

    def test_select_spec_with_optional_fails_with_expected_vs_actual_table_comparison(self):
        triples = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        test-data:sub1 test-data:pred test-data:obj ; test-data:predicate test-data:object.
        test-data:sub2 test-data:pred test-data:obj .
        """
        given = Graph().parse(data=triples, format="ttl")
        spec = """
            @prefix sh: <http://www.w3.org/ns/shacl#> .
            @prefix must: <https://mustrd.com/model/> .
            @prefix test-data: <https://semanticpartners.com/data/test/> .

            test-data:my_failing_spec
                a must:TestSpec ;
                must:when  [ a must:TextSparqlSource ;
                        must:queryText  "select ?s ?o ?object { ?s <https://semanticpartners.com/data/test/pred> ?o . OPTIONAL {?s <https://semanticpartners.com/data/test/predicate> ?object} }" ;
                        must:queryType must:SelectSparql ] ;
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
        """ # noqa
        spec_graph = Graph().parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_spec
        when_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.when,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        self.triple_store["given"] = given
        spec = Specification(spec_uri, self.triple_store, given, when_component, then_component)
        when_result = run_when(spec_uri, self.triple_store, when_component[0])
        then_result = check_result(spec, when_result)

        if isinstance(then_result, SelectSpecFailure):
            table_diff = then_result.table_comparison.to_markdown()
            message = then_result.message
            assert isinstance(then_component, TableThenSpec)
            assert then_result.spec_uri == spec_uri
            assert message == "Expected 2 row(s) and 3 column(s), got 2 row(s) and 3 column(s)"
            assert table_diff == """|    | ('o', 'expected')                             | ('o', 'actual')                            |
|---:|:----------------------------------------------|:-------------------------------------------|
|  1 | https://semanticpartners.com/data/test/object | https://semanticpartners.com/data/test/obj |""" # noqa
        else:
            raise Exception(f"wrong spec result type {then_result}")

    def test_select_spec_expected_different_column_names_fails(self):

        given = Graph().parse(data=self.given_sub_pred_obj, format="ttl")
        spec = """
            @prefix sh: <http://www.w3.org/ns/shacl#> .
            @prefix must: <https://mustrd.com/model/> .
            @prefix test-data: <https://semanticpartners.com/data/test/> .

            test-data:my_failing_spec
                a must:TestSpec ;
                must:when  [ a must:TextSparqlSource ;
                        must:queryText  "select ?s ?p ?o { ?s ?p ?o }" ;
                        must:queryType must:SelectSparql ] ;
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
        spec_graph = Graph().parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_spec
        when_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.when,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        self.triple_store["given"] = given
        spec = Specification(spec_uri, self.triple_store, given, when_component, then_component)
        when_result = run_when(spec_uri, self.triple_store, when_component[0])
        then_result = check_result(spec, when_result)

        if isinstance(then_result, SelectSpecFailure):
            table_diff = then_result.table_comparison.to_markdown()
            message = then_result.message
            assert isinstance(then_component, TableThenSpec)
            assert then_result.spec_uri == spec_uri
            assert message == "Expected 1 row(s) and 3 column(s), got 1 row(s) and 3 column(s)"
            assert table_diff == """|    | ('obj', 'expected')                        | ('obj', 'actual')   | ('obj_datatype', 'expected')            | ('obj_datatype', 'actual')   | ('p', 'expected')                           | ('p', 'actual')                             | ('p_datatype', 'expected')              | ('p_datatype', 'actual')                | ('s', 'expected')                          | ('s', 'actual')                            | ('s_datatype', 'expected')              | ('s_datatype', 'actual')                | ('o', 'expected')   | ('o', 'actual')                            | ('o_datatype', 'expected')   | ('o_datatype', 'actual')                |
|---:|:-------------------------------------------|:--------------------|:----------------------------------------|:-----------------------------|:--------------------------------------------|:--------------------------------------------|:----------------------------------------|:----------------------------------------|:-------------------------------------------|:-------------------------------------------|:----------------------------------------|:----------------------------------------|:--------------------|:-------------------------------------------|:-----------------------------|:----------------------------------------|
|  0 | https://semanticpartners.com/data/test/obj |                     | http://www.w3.org/2001/XMLSchema#anyURI |                              | https://semanticpartners.com/data/test/pred | https://semanticpartners.com/data/test/pred | http://www.w3.org/2001/XMLSchema#anyURI | http://www.w3.org/2001/XMLSchema#anyURI | https://semanticpartners.com/data/test/sub | https://semanticpartners.com/data/test/sub | http://www.w3.org/2001/XMLSchema#anyURI | http://www.w3.org/2001/XMLSchema#anyURI |                     | https://semanticpartners.com/data/test/obj |                              | http://www.w3.org/2001/XMLSchema#anyURI |""" # noqa
        else:
            raise Exception(f"wrong spec result type {then_result}")

    def test_select_spec_expected_fewer_rows_and_columns_fails(self):

        triples = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        test-data:sub test-data:pred test-data:obj , test-data:object .
        """
        given = Graph().parse(data=triples, format="ttl")
        spec = """
            @prefix sh: <http://www.w3.org/ns/shacl#> .
            @prefix must: <https://mustrd.com/model/> .
            @prefix test-data: <https://semanticpartners.com/data/test/> .

            test-data:my_failing_spec
                a must:TestSpec ;
                must:when  [ a must:TextSparqlSource ;
                        must:queryText  "select ?s ?p ?o { ?s ?p ?o }" ;
                        must:queryType must:SelectSparql ] ;
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
        spec_graph = Graph().parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_spec
        when_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.when,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        self.triple_store["given"] = given
        spec = Specification(spec_uri, self.triple_store, given, when_component, then_component)
        when_result = run_when(spec_uri, self.triple_store, when_component[0])
        then_result = check_result(spec, when_result)

        if isinstance(then_result, SelectSpecFailure):
            table_diff = then_result.table_comparison.to_markdown()
            message = then_result.message
            assert isinstance(then_component, TableThenSpec)
            assert then_result.spec_uri == spec_uri
            assert message == "Expected 1 row(s) and 2 column(s), got 2 row(s) and 3 column(s)"
            assert table_diff == """|    | ('o', 'expected')                          | ('o', 'actual')                               | ('o_datatype', 'expected')              | ('o_datatype', 'actual')                | ('s', 'expected')                          | ('s', 'actual')                            | ('s_datatype', 'expected')              | ('s_datatype', 'actual')                | ('p', 'expected')   | ('p', 'actual')                             | ('p_datatype', 'expected')   | ('p_datatype', 'actual')                |
|---:|:-------------------------------------------|:----------------------------------------------|:----------------------------------------|:----------------------------------------|:-------------------------------------------|:-------------------------------------------|:----------------------------------------|:----------------------------------------|:--------------------|:--------------------------------------------|:-----------------------------|:----------------------------------------|
|  0 |                                            | https://semanticpartners.com/data/test/obj    |                                         | http://www.w3.org/2001/XMLSchema#anyURI |                                            | https://semanticpartners.com/data/test/sub |                                         | http://www.w3.org/2001/XMLSchema#anyURI |                     | https://semanticpartners.com/data/test/pred |                              | http://www.w3.org/2001/XMLSchema#anyURI |
|  1 |                                            | https://semanticpartners.com/data/test/object |                                         | http://www.w3.org/2001/XMLSchema#anyURI |                                            | https://semanticpartners.com/data/test/sub |                                         | http://www.w3.org/2001/XMLSchema#anyURI |                     | https://semanticpartners.com/data/test/pred |                              | http://www.w3.org/2001/XMLSchema#anyURI |
|  2 | https://semanticpartners.com/data/test/obj |                                               | http://www.w3.org/2001/XMLSchema#anyURI |                                         | https://semanticpartners.com/data/test/sub |                                            | http://www.w3.org/2001/XMLSchema#anyURI |                                         |                     |                                             |                              |                                         |""" # noqa
        else:
            raise Exception(f"wrong spec result type {then_result}")

    def test_select_spec_expected_fewer_and_different_rows_and_columns_fails(self):
        triples = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        test-data:sub test-data:pred test-data:obj , test-data:object .
        """
        given = Graph().parse(data=triples, format="ttl")

        spec = """
            @prefix sh: <http://www.w3.org/ns/shacl#> .
            @prefix must: <https://mustrd.com/model/> .
            @prefix test-data: <https://semanticpartners.com/data/test/> .

            test-data:my_failing_spec
                a must:TestSpec ;
                must:when  [ a must:TextSparqlSource ;
                        must:queryText  "select ?s ?p ?o { ?s ?p ?o }" ;
                        must:queryType must:SelectSparql ] ;
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
        spec_graph = Graph().parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_spec
        when_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.when,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        self.triple_store["given"] = given
        spec = Specification(spec_uri, self.triple_store, given, when_component, then_component)
        when_result = run_when(spec_uri, self.triple_store, when_component[0])
        then_result = check_result(spec, when_result)

        if isinstance(then_result, SelectSpecFailure):
            table_diff = then_result.table_comparison.to_markdown()
            message = then_result.message
            assert isinstance(then_component, TableThenSpec)
            assert then_result.spec_uri == spec_uri
            assert message == "Expected 1 row(s) and 2 column(s), got 2 row(s) and 3 column(s)"
            assert table_diff == """|    | ('o', 'expected')                          | ('o', 'actual')                               | ('o_datatype', 'expected')              | ('o_datatype', 'actual')                | ('s', 'expected')                              | ('s', 'actual')                            | ('s_datatype', 'expected')              | ('s_datatype', 'actual')                | ('p', 'expected')   | ('p', 'actual')                             | ('p_datatype', 'expected')   | ('p_datatype', 'actual')                |
|---:|:-------------------------------------------|:----------------------------------------------|:----------------------------------------|:----------------------------------------|:-----------------------------------------------|:-------------------------------------------|:----------------------------------------|:----------------------------------------|:--------------------|:--------------------------------------------|:-----------------------------|:----------------------------------------|
|  0 |                                            | https://semanticpartners.com/data/test/obj    |                                         | http://www.w3.org/2001/XMLSchema#anyURI |                                                | https://semanticpartners.com/data/test/sub |                                         | http://www.w3.org/2001/XMLSchema#anyURI |                     | https://semanticpartners.com/data/test/pred |                              | http://www.w3.org/2001/XMLSchema#anyURI |
|  1 |                                            | https://semanticpartners.com/data/test/object |                                         | http://www.w3.org/2001/XMLSchema#anyURI |                                                | https://semanticpartners.com/data/test/sub |                                         | http://www.w3.org/2001/XMLSchema#anyURI |                     | https://semanticpartners.com/data/test/pred |                              | http://www.w3.org/2001/XMLSchema#anyURI |
|  2 | https://semanticpartners.com/data/test/obj |                                               | http://www.w3.org/2001/XMLSchema#anyURI |                                         | https://semanticpartners.com/data/test/subject |                                            | http://www.w3.org/2001/XMLSchema#anyURI |                                         |                     |                                             |                              |                                         |""" # noqa
        else:
            raise Exception(f"wrong spec result type {then_result}")

    def test_select_spec_ordered_passes(self):
        triples = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        test-data:sub2 test-data:pred2 test-data:obj2 .
        test-data:sub1 test-data:pred1 test-data:obj1 .
        """
        given = Graph().parse(data=triples, format="ttl")
        spec = """
            @prefix sh: <http://www.w3.org/ns/shacl#> .
            @prefix must: <https://mustrd.com/model/> .
            @prefix test-data: <https://semanticpartners.com/data/test/> .

            test-data:my_first_spec
                a must:TestSpec ;
                must:when  [ a must:TextSparqlSource ;
                        must:queryText  "select ?s ?p ?o { ?s ?p ?o } ORDER BY ?p" ;
                        must:queryType must:SelectSparql ] ;
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
        spec_graph = Graph().parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_first_spec
        when_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.when,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        self.triple_store["given"] = given
        spec = Specification(spec_uri, self.triple_store, given, when_component, then_component)
        when_result = run_when(spec_uri, self.triple_store, when_component[0])
        then_result = check_result(spec, when_result)

        expected_result = SpecPassed(spec_uri, self.triple_store["type"])
        assert then_result == expected_result
        assert isinstance(then_component, TableThenSpec)

    def test_select_spec_ordered_passes_with_warning(self):

        triples = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        test-data:sub1 test-data:pred1 test-data:obj1 .
        test-data:sub2 test-data:pred2 test-data:obj2 .
        """
        given = Graph().parse(data=triples, format="ttl")
        spec = """
            @prefix sh: <http://www.w3.org/ns/shacl#> .
            @prefix must: <https://mustrd.com/model/> .
            @prefix test-data: <https://semanticpartners.com/data/test/> .

            test-data:my_first_spec
                a must:TestSpec ;
                must:when  [ a must:TextSparqlSource ;
                        must:queryText  "select ?s ?p ?o { ?s ?p ?o }" ;
                        must:queryType must:SelectSparql ] ;
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
        spec_graph = Graph().parse(data=spec, format='ttl')
        spec_uri = TEST_DATA.my_first_spec
        warning = f"sh:order in {spec_uri} is ignored, no ORDER BY in query"
        when_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.when,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        self.triple_store["given"] = given
        spec = Specification(spec_uri, self.triple_store, given, when_component, then_component)
        when_result = run_when(spec_uri, self.triple_store, when_component[0])
        then_result = check_result(spec, when_result)

        expected_result = SpecPassedWithWarning(spec_uri, self.triple_store["type"], warning)
        assert then_result == expected_result
        assert isinstance(then_component, TableThenSpec)

    def test_select_spec_ordered_fails(self):
        triples = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        test-data:sub1 test-data:pred1 test-data:obj1 .
        test-data:sub2 test-data:pred2 test-data:obj2 .
        """
        given = Graph().parse(data=triples, format="ttl")
        spec = """
            @prefix sh: <http://www.w3.org/ns/shacl#> .
            @prefix must: <https://mustrd.com/model/> .
            @prefix test-data: <https://semanticpartners.com/data/test/> .

            test-data:my_failing_spec
                a must:TestSpec ;
                must:when  [ a must:TextSparqlSource ;
                        must:queryText  "select ?s ?p ?o { ?s ?p ?o } ORDER BY ?p" ;
                        must:queryType must:SelectSparql ] ;
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
        spec_graph = Graph().parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_spec
        when_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.when,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        self.triple_store["given"] = given
        spec = Specification(spec_uri, self.triple_store, given, when_component, then_component)
        when_result = run_when(spec_uri, self.triple_store, when_component[0])
        then_result = check_result(spec, when_result)

        if isinstance(then_result, SelectSpecFailure):
            table_diff = then_result.table_comparison.to_markdown()
            message = then_result.message
            assert isinstance(then_component, TableThenSpec)
            assert then_result.spec_uri == spec_uri
            assert message == "Expected 2 row(s) and 3 column(s), got 2 row(s) and 3 column(s)"
            assert table_diff == """|    | ('s', 'expected')                           | ('s', 'actual')                             | ('p', 'expected')                            | ('p', 'actual')                              | ('o', 'expected')                           | ('o', 'actual')                             |
|---:|:--------------------------------------------|:--------------------------------------------|:---------------------------------------------|:---------------------------------------------|:--------------------------------------------|:--------------------------------------------|
|  0 | https://semanticpartners.com/data/test/sub2 | https://semanticpartners.com/data/test/sub1 | https://semanticpartners.com/data/test/pred2 | https://semanticpartners.com/data/test/pred1 | https://semanticpartners.com/data/test/obj2 | https://semanticpartners.com/data/test/obj1 |
|  1 | https://semanticpartners.com/data/test/sub1 | https://semanticpartners.com/data/test/sub2 | https://semanticpartners.com/data/test/pred1 | https://semanticpartners.com/data/test/pred2 | https://semanticpartners.com/data/test/obj1 | https://semanticpartners.com/data/test/obj2 |""" # noqa
        else:
            raise Exception(f"wrong spec result type {then_result}")

    def test_select_spec_not_ordered_fails(self):
        triples = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        test-data:sub1 test-data:pred1 test-data:obj1 .
        test-data:sub2 test-data:pred2 test-data:obj2 .
        """
        given = Graph().parse(data=triples, format="ttl")
        spec = """
            @prefix sh: <http://www.w3.org/ns/shacl#> .
            @prefix must: <https://mustrd.com/model/> .
            @prefix test-data: <https://semanticpartners.com/data/test/> .

            test-data:my_failing_spec
                a must:TestSpec ;
                must:when  [ a must:TextSparqlSource ;
                        must:queryText  "select ?s ?p ?o { ?s ?p ?o } ORDER BY ?p" ;
                        must:queryType must:SelectSparql ] ;
            must:then  [ a must:TableDataset ;
                 must:hasRow  [ must:hasBinding[ must:variable "s" ;
                                        must:boundValue  test-data:sub2 ; ],
                                      [ must:variable "p" ;
                                        must:boundValue  test-data:pred2 ; ],
                                      [ must:variable "o" ;
                                        must:boundValue  test-data:obj2 ; ] ; ] ,

                 [ must:hasBinding[ must:variable "s" ;
                                        must:boundValue  test-data:sub1 ; ],
                                      [ must:variable "p" ;
                                        must:boundValue  test-data:pred1 ; ],
                                      [ must:variable "o" ;
                                        must:boundValue  test-data:obj1 ; ] ; ] ;
 ] .
        """
        spec_graph = Graph().parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_spec
        when_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.when,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        self.triple_store["given"] = given
        spec = Specification(spec_uri, self.triple_store, given, when_component, then_component)
        when_result = run_when(spec_uri, self.triple_store, when_component[0])
        then_result = check_result(spec, when_result)
        assert isinstance(then_result, SelectSpecFailure)
        assert isinstance(then_component, TableThenSpec)
        assert then_result.spec_uri == spec_uri
        assert then_result.message == "Actual result is ordered, must:then must contain sh:order on every row."

    def test_select_spec_not_all_ordered_fails(self):

        triples = """
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        test-data:sub1 test-data:pred1 test-data:obj1 .
        test-data:sub2 test-data:pred2 test-data:obj2 .
        """
        given = Graph().parse(data=triples, format="ttl")
        spec = """
            @prefix sh: <http://www.w3.org/ns/shacl#> .
            @prefix must: <https://mustrd.com/model/> .
            @prefix test-data: <https://semanticpartners.com/data/test/> .

            test-data:my_failing_spec
                a must:TestSpec ;
                must:when  [ a must:TextSparqlSource ;
                        must:queryText  "select ?s ?p ?o { ?s ?p ?o } ORDER BY ?p" ;
                        must:queryType must:SelectSparql ] ;
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
        spec_graph = Graph().parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_spec
        when_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.when,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        self.triple_store["given"] = given
        spec = Specification(spec_uri, self.triple_store, given, when_component, then_component)
        when_result = run_when(spec_uri, self.triple_store, when_component[0])
        then_result = check_result(spec, when_result)

        assert isinstance(then_result, SelectSpecFailure)
        assert isinstance(then_component, TableThenSpec)
        assert then_result.spec_uri == spec_uri
        assert then_result.message == "Actual result is ordered, must:then must contain sh:order on every row."

    def test_select_spec_expected_fewer_rows_fails_ordered(self):

        triples = """
            @prefix test-data: <https://semanticpartners.com/data/test/> .
            test-data:sub test-data:pred test-data:obj .
            test-data:subject test-data:predicate test-data:object .
            """
        given = Graph().parse(data=triples, format="ttl")
        spec = """
            @prefix sh: <http://www.w3.org/ns/shacl#> .
            @prefix must: <https://mustrd.com/model/> .
            @prefix test-data: <https://semanticpartners.com/data/test/> .

            test-data:my_failing_spec
                a must:TestSpec ;
                must:when  [ a must:TextSparqlSource ;
                        must:queryText  "select ?s ?p ?o { ?s ?p ?o } order by ?p" ;
                        must:queryType must:SelectSparql ] ;
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
        spec_graph = Graph().parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_spec
        when_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.when,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        self.triple_store["given"] = given
        spec = Specification(spec_uri, self.triple_store, given, when_component, then_component)
        when_result = run_when(spec_uri, self.triple_store, when_component[0])
        then_result = check_result(spec, when_result)

        assert isinstance(then_result, SelectSpecFailure)
        assert isinstance(then_component, TableThenSpec)
        assert then_result.spec_uri == spec_uri
        assert then_result.message == "Actual result is ordered, must:then must contain sh:order on every row."

    def test_select_given_file_then_file_spec_passes(self):

        run_config = {'spec_path': ""}
        given_path = "test/data/given.ttl"
        file_path = Path(given_path)
        triples = get_spec_component_from_file(file_path)
        given = Graph().parse(data=triples, format="ttl")
        spec = """
            @prefix sh: <http://www.w3.org/ns/shacl#> .
            @prefix must: <https://mustrd.com/model/> .
            @prefix test-data: <https://semanticpartners.com/data/test/> .

            test-data:my_first_spec
                a must:TestSpec ;
                must:when  [ a must:TextSparqlSource ;
                        must:queryText  "select ?s ?p ?o { ?s ?p ?o }" ;
                        must:queryType must:SelectSparql ] ;
            must:then  [ a must:FileDataset ;
                                   must:file "test/data/thenSuccess.csv" ] .
            """

        spec_uri = TEST_DATA.my_first_spec
        spec_graph = parse_spec(spec, spec_uri, __name__)

        when_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.when,
                                              spec_graph=spec_graph,
                                              run_config=run_config,
                                              mustrd_triple_store=self.triple_store)

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              run_config=run_config,
                                              mustrd_triple_store=self.triple_store)

        self.triple_store["given"] = given
        spec = Specification(spec_uri, self.triple_store, given, when_component, then_component)
        when_result = run_when(spec_uri, self.triple_store, when_component[0])
        then_result = check_result(spec, when_result)

        expected_result = SpecPassed(spec_uri, self.triple_store["type"])
        assert then_result == expected_result
        assert isinstance(then_component, TableThenSpec)

    def test_select_given_file_then_file_spec_fails(self):
        run_config = {'spec_path': "/"}
        given_path = "test/data/given.ttl"
        file_path = Path(given_path)
        triples = get_spec_component_from_file(file_path)
        given = Graph().parse(data=triples, format="ttl")
        spec = """
            @prefix sh: <http://www.w3.org/ns/shacl#> .
            @prefix must: <https://mustrd.com/model/> .
            @prefix test-data: <https://semanticpartners.com/data/test/> .

            test-data:my_first_spec
                a must:TestSpec ;
                must:when  [ a must:TextSparqlSource ;
                        must:queryText  "select ?s ?p ?o { ?s ?p ?o }" ;
                        must:queryType must:SelectSparql ] ;
            must:then  [ a must:FileDataset ;
                                   must:file "test/data/thenFail.csv" ] .
        """

        spec_uri = TEST_DATA.my_first_spec
        spec_graph = parse_spec(spec, spec_uri, __name__)

        when_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.when,
                                              spec_graph=spec_graph,
                                              run_config=None,
                                              mustrd_triple_store=self.triple_store)

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              run_config=run_config,
                                              mustrd_triple_store=self.triple_store)

        self.triple_store["given"] = given
        spec = Specification(spec_uri, self.triple_store, given, when_component, then_component)
        when_result = run_when(spec_uri, self.triple_store, when_component[0])
        then_result = check_result(spec, when_result)

        if isinstance(then_result, SelectSpecFailure):
            table_diff = then_result.table_comparison.to_markdown()
            message = then_result.message
            assert isinstance(then_component, TableThenSpec)
            assert then_result.spec_uri == spec_uri
            assert message == "Expected 1 row(s) and 3 column(s), got 1 row(s) and 3 column(s)"
            assert table_diff == """|    | ('o', 'expected')                           | ('o', 'actual')                            |
|---:|:--------------------------------------------|:-------------------------------------------|
|  0 | https://semanticpartners.com/data/test/obj2 | https://semanticpartners.com/data/test/obj |""" # noqa
        else:
            raise Exception(f"wrong spec result type {then_result}")
