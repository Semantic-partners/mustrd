from pathlib import Path

import pytest
from rdflib import Graph, Literal
from rdflib.compare import isomorphic
from rdflib.namespace import Namespace

from mustrd.mustrd import Specification, run_spec
from mustrd.namespace import MUST, TRIPLESTORE
from mustrd.spec_component import parse_spec_component, ThenSpec

from test.addspec_source_file_to_spec_graph import addspec_source_file_to_spec_graph
import logging
TEST_DATA = Namespace("https://semanticpartners.com/data/test/")

log = logging.getLogger(__name__)


class TestRunSpec:
    given_sub_pred_obj = """
    @prefix test-data: <https://semanticpartners.com/data/test/> .
    test-data:sub test-data:pred test-data:obj .
    """

    then_obj_sub_pred = """
    @prefix test-data: <https://semanticpartners.com/data/test/> .
    test-data:obj test-data:sub test-data:pred .
    """

    triple_store = {"type": TRIPLESTORE.RdfLib}

    def test_no_rdf_type_error(self):
        spec_graph = Graph()
        spec = """
        @prefix must: <https://mustrd.org/model/> .
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
        run_config = {'spec_path': "/"}
        spec_graph = Graph()
        spec = """
        @prefix must: <https://mustrd.org/model/> .
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
        run_config = {'spec_path': "/"}
        spec_graph = Graph()
        spec = """
        @prefix must: <https://mustrd.org/model/> .
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
        run_config = {'spec_path': "/"}
        spec_graph = Graph()
        spec = """
        @prefix must: <https://mustrd.org/model/> .
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
        run_config = {'spec_path': "/"}
        spec_graph = Graph()
        spec = """
        @prefix must: <https://mustrd.org/model/> .
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
        run_config = {'spec_path': "/"}
        spec_graph = Graph()
        spec = """
        @prefix must: <https://mustrd.org/model/> .
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

        with pytest.raises(ValueError):
            parse_spec_component(subject=spec_uri,
                                 predicate=MUST.then,
                                 spec_graph=spec_graph,
                                 run_config=run_config,
                                 mustrd_triple_store=self.triple_store)

    def test_spec_file_from_folder_passes(self):
        run_config = {'then_path': Path("data"),
                      # FIXME: spec_path seems mandatory, is that normal?
                      'spec_path': Path("test/")}

        spec_graph = Graph()
        spec = """
        @prefix must: <https://mustrd.org/model/> .
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

        assert isinstance(then_component, ThenSpec)
        assert isomorphic(then, then_component.value)

    def test_invalid_data_source_predicate_combination_error(self):
        spec_graph = Graph()
        spec = """
        @prefix must: <https://mustrd.org/model/> .
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
        assert "Invalid combination of data source type" in str(error_message.value)
        assert "Valid combinations are:" in str(error_message.value)

    def test_invalid_query_type_ask_error(self):
        state = Graph()
        state.parse(data=self.given_sub_pred_obj, format="ttl")

        spec_graph = Graph()
        spec = """
                @prefix must: <https://mustrd.org/model/> .
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

        specification = Specification(
            spec_uri, self.triple_store, state, when_component, then_component)

        result = run_spec(specification)
        logging.info(f"Result: {result} {type(result)}")
        # don't love the args[2] magic here. open to suggestions for improvement. looks like a weird mix of returning either a tuple or an exception
        assert result.args[2] == "NotImplementedError: SPARQL ASK not implemented."

    def test_invalid_query_type_delete_error(self):
        state = Graph()
        state.parse(data=self.given_sub_pred_obj, format="ttl")

        spec_graph = Graph()
        spec = """
                @prefix must: <https://mustrd.org/model/> .
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

        specification = Specification(
            spec_uri, self.triple_store, state, when_component, then_component)

        result = run_spec(specification)
        # don't love the args[2] magic here. open to suggestions for improvement
        assert result.args[2] == "NotImplementedError: https://mustrd.org/model/DeleteSparql is not a valid SPARQL query type."
