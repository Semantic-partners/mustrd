import os
from pathlib import Path

import pytest
from rdflib import Graph
from rdflib.compare import isomorphic
from rdflib.namespace import Namespace

from namespace import MUST
from spec_component import parse_spec_component, ThenSpec
from utils import get_project_root

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

    def test_no_rdf_type_fails(self):
        spec_graph = Graph()
        spec = """
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

        test-data:my_first_spec 
            a must:TestSpec ;
                must:then  [ must:statements [ a             rdf:Statement ;
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
                                 folder_location=None,
                                 mustrd_triple_store=self.triple_store)

    def test_file_not_found(self):
        spec_graph = Graph()
        spec = """
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

        test-data:my_failing_spec 
            a must:TestSpec ;
                must:then  [ a must:FileDataSource ;
                                   must:file "test/data/missingFile.nt" ] .
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_spec

        with pytest.raises(FileNotFoundError):
            parse_spec_component(subject=spec_uri,
                                 predicate=MUST.then,
                                 spec_graph=spec_graph,
                                 folder_location=None,
                                 mustrd_triple_store=self.triple_store)

    def test_spec_from_file_fails(self):
        spec_graph = Graph()
        spec = """
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

        test-data:my_failing_spec 
            a must:TestSpec ;
                must:then  [ a must:FileDataSource ;
                                   must:file "test/data" ] .
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_spec

        with pytest.raises(ValueError):
            parse_spec_component(subject=spec_uri,
                                 predicate=MUST.then,
                                 spec_graph=spec_graph,
                                 folder_location=None,
                                 mustrd_triple_store=self.triple_store)

    def test_spec_wrong_file_format_fails(self):
        spec_graph = Graph()
        spec = """
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

        test-data:my_failing_spec 
            a must:TestSpec ;
                must:then  [ a must:FileDataSource ;
                                   must:file "test/test_spec.py" ] .
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_spec

        with pytest.raises(ValueError):
            parse_spec_component(subject=spec_uri,
                                 predicate=MUST.then,
                                 spec_graph=spec_graph,
                                 folder_location=None,
                                 mustrd_triple_store=self.triple_store)

    def test_spec_folder_path_missing_fails(self):
        spec_graph = Graph()
        spec = """
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

        test-data:my_failing_spec 
            a must:TestSpec ;
                must:then  [ a must:FolderDataSource ;
                                   must:file "thenSuccess.nt" ] .
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_spec

        with pytest.raises(ValueError):
            parse_spec_component(subject=spec_uri,
                                 predicate=MUST.then,
                                 spec_graph=spec_graph,
                                 folder_location=None,
                                 mustrd_triple_store=self.triple_store)

    def test_spec_file_from_folder_passes(self):
        project_root = get_project_root()
        folder_path = Path(os.path.join(project_root, "test/data"))

        spec_graph = Graph()
        spec = """
        @prefix must: <https://mustrd.com/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

        test-data:my_failing_spec 
            a must:TestSpec ;
                must:then  [ a must:FolderDataSource ;
                                   must:fileName "thenSuccess.nt" ] .
        """
        spec_graph.parse(data=spec, format='ttl')

        spec_uri = TEST_DATA.my_failing_spec

        then_component = parse_spec_component(subject=spec_uri,
                                              predicate=MUST.then,
                                              spec_graph=spec_graph,
                                              folder_location=folder_path,
                                              mustrd_triple_store=self.triple_store)

        then = Graph()
        then.parse(data=self.then_obj_sub_pred, format="ttl")

        assert type(then_component) == ThenSpec
        assert isomorphic(then, then_component.value)
