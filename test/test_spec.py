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
from pathlib import Path

import pytest
from rdflib import Graph, URIRef, Literal
from rdflib.compare import isomorphic
from rdflib.namespace import Namespace

from mustrd.mustrd import Specification, run_when, SpecSkipped, run_spec
from mustrd.namespace import MUST
from mustrd.spec_component import parse_spec_component, ThenSpec
from mustrd.utils import get_project_root

from test.addspec_source_file_to_spec_graph import addspec_source_file_to_spec_graph

TEST_DATA = Namespace("https://semanticpartners.com/data/test/")

class TestRunSpec:
    given_sub_pred_obj = """
    @prefix test-data: <https://semanticpartners.com/data/test/> .
    test-data:sub test-data:pred test-data:obj .
    """

    then_obj_sub_pred = """
    @prefix test-data: <https://semanticpartners.com/data/test/> .
    test-data:obj test-data:sub test-data:pred .
    """

    triple_store = {"type": MUST.RdfLib}

    def test_no_rdf_type_error(self):
        spec_graph = Graph()
        spec = """
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

        test-data:my_first_spec 
            a must:TestSpec ;
                must:then  [ must:hasStatement [ a             rdf:Statement ;
                                   rdf:subject   test-data:obj1 ;
                                   rdf:predicate test-data:sub1 ;
                                   rdf:object    test-data:pred1 ; ] ; ]  .
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_first_spec

        with pytest.raises(ValueError):
            parse_spec_component(subject=spec_uri,
                                 predicate=MUST.then,
                                 spec_graph=spec_graph,
                                 run_config=None,
                                 mustrd_triple_store=self.triple_store)

    def test_file_not_found_error(self):
        project_root = get_project_root()
        run_config = {'spec_path': project_root}
        spec_graph = Graph()
        spec = """
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

        test-data:my_failing_spec 
            a must:TestSpec ;
                must:then  [ a must:FileDataset ;
                                   must:file "../../test/data/missingFile.nt" ] .
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_spec
        addspec_source_file_to_spec_graph(spec_graph, spec_uri, __name__)

        with pytest.raises(FileNotFoundError):
            parse_spec_component(subject=spec_uri,
                                 predicate=MUST.then,
                                 spec_graph=spec_graph,
                                 run_config=run_config,
                                 mustrd_triple_store=self.triple_store)

    
    def test_spec_then_from_file_error(self):
        project_root = get_project_root()
        run_config = {'spec_path': project_root}
        spec_graph = Graph()
        spec = """
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

        test-data:my_failing_spec 
            a must:TestSpec ;
                must:then  [ a must:FileDataset ;
                                   must:file "../../test/data" ] .
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_spec
        spec_graph.add([spec_uri, MUST.specSourceFile, Literal(__name__)])

        with pytest.raises(FileNotFoundError):
            parse_spec_component(subject=spec_uri,
                                 predicate=MUST.then,
                                 spec_graph=spec_graph,
                                 run_config=run_config,
                                 mustrd_triple_store=self.triple_store)

    def test_spec_given_from_file_error(self):
        project_root = get_project_root()
        run_config = {'spec_path': project_root}
        spec_graph = Graph()
        spec = """
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

        test-data:my_failing_spec 
            a must:TestSpec ;
                must:then  [ a must:FileDataset ;
                                   must:file "../../test/data" ] .
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_spec
        addspec_source_file_to_spec_graph(spec_graph, spec_uri, __name__)
        
        with pytest.raises(FileNotFoundError):
            parse_spec_component(subject=spec_uri,
                                 predicate=MUST.then,
                                 spec_graph=spec_graph,
                                 run_config=run_config,
                                 mustrd_triple_store=self.triple_store)

    def test_spec_wrong_file_format_error(self):
        project_root = get_project_root()
        run_config = {'spec_path': project_root}
        spec_graph = Graph()
        spec = """
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

        test-data:my_failing_spec 
            a must:TestSpec ;
                must:then  [ a must:FileDataset ;
                                   must:file "test/test_spec.py" ] .
        """
        spec_graph.parse(data=spec, format='ttl')
        spec_uri = TEST_DATA.my_failing_spec
        addspec_source_file_to_spec_graph(spec_graph, spec_uri, __name__)

        with pytest.raises(ValueError):
            parse_spec_component(subject=spec_uri,
                                 predicate=MUST.then,
                                 spec_graph=spec_graph,
                                 run_config=run_config,
                                 mustrd_triple_store=self.triple_store)

    def test_spec_folder_path_missing_error(self):
        project_root = get_project_root()
        run_config = {'spec_path': project_root}
        spec_graph = Graph()
        spec = """
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

        test-data:my_failing_spec 
            a must:TestSpec ;
                must:then  [ a must:FolderDataset ;
                                   must:file "thenSuccess.nt" ] .
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_spec
        addspec_source_file_to_spec_graph(spec_graph, spec_uri, __name__)

        with pytest.raises(KeyError):
            parse_spec_component(subject=spec_uri,
                                 predicate=MUST.then,
                                 spec_graph=spec_graph,
                                 run_config=run_config,
                                 mustrd_triple_store=self.triple_store)

    def test_spec_file_from_folder_passes(self):
        project_root = get_project_root()
        run_config = {'then_path': Path("data"),
                      # FIXME: spec_path seems mandatory, is that normal?
                      'spec_path': Path(os.path.join(project_root, "test/"))}

        spec_graph = Graph()
        spec = """
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

        test-data:my_failing_spec 
            a must:TestSpec ;
                must:then  [ a must:FolderDataset ;
                                   must:fileName "thenSuccess.nt" ] .
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_spec
        addspec_source_file_to_spec_graph(spec_graph, spec_uri, __name__)

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              run_config=run_config,
                                              mustrd_triple_store=self.triple_store)

        then = Graph()
        then.parse(data=self.then_obj_sub_pred, format="ttl")

        assert type(then_component) == ThenSpec
        assert isomorphic(then, then_component.value)

    def test_invalid_data_source_predicate_combination_error(self):
        spec_graph = Graph()
        spec = """
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

        test-data:my_first_spec 
            a must:TestSpec ;
                 must:given  [ a must:TableDataset ;
                                   must:hasRow [ must:hasBinding[
                                        must:variable "s" ;
                                        must:boundValue  test-data:sub ; ],
                                      [ must:variable "p" ;
                                        must:boundValue  test-data:pred ; ],
                                      [ must:variable "o" ;
                                        must:boundValue  test-data:obj ; ] ;
               ] ; ] .
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_first_spec
        addspec_source_file_to_spec_graph(spec_graph, spec_uri, __name__)

        with pytest.raises(ValueError) as error_message:
            parse_spec_component(subject=spec_uri,
                                 predicate=MUST.given,
                                 spec_graph=spec_graph,
                                 run_config=None,
                                 mustrd_triple_store=self.triple_store)
        assert str(
            error_message.value) == f"Invalid combination of data source type ({MUST.TableDataset}) and spec component ({MUST.given})"

    def test_invalid_query_type_ask_error(self):
        state = Graph()
        state.parse(data=self.given_sub_pred_obj, format="ttl")

        spec_graph = Graph()
        spec = """
                @prefix must: <https://mustrd.com/model/> .
                @prefix test-data: <https://semanticpartners.com/data/test/> .
                @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

                test-data:my_first_spec 
                    a must:TestSpec ;
                        must:when [ a must:TextSparqlSource ;
                                    must:queryText  "ask { ?s ?p 25 }" ;
                                    must:queryType must:AskSparql ; ] ;
                        must:then  [ a must:EmptyGraph ] .
                """
        spec_graph.parse(data=spec, format='ttl')

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

        specification = Specification(spec_uri, self.triple_store, state, when_component, then_component)

        result = run_spec(specification)
        # assert type(result) == SpecSkipped
        assert result.message == "SPARQL ASK not implemented."

    def test_invalid_query_type_delete_error(self):
        state = Graph()
        state.parse(data=self.given_sub_pred_obj, format="ttl")

        spec_graph = Graph()
        spec = """
                @prefix must: <https://mustrd.com/model/> .
                @prefix test-data: <https://semanticpartners.com/data/test/> .
                @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

                test-data:my_first_spec 
                    a must:TestSpec ;
                        must:when [ a must:TextSparqlSource ;
                                    must:queryText  "delete { ?s ?p 25 }" ;
                                    must:queryType must:DeleteSparql ; ] ;
                        must:then  [ a must:EmptyGraph ] .
                """
        spec_graph.parse(data=spec, format='ttl')

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

        specification = Specification(spec_uri, self.triple_store, state, when_component, then_component)

        result = run_spec(specification)
        assert type(result) == SpecSkipped
        assert result.message == "https://mustrd.com/model/DeleteSparql is not a valid SPARQL query type."
