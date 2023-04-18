import pytest
from rdflib import Graph
from rdflib.namespace import Namespace

from namespace import MUST
from spec_component import parse_spec_component

TEST_DATA = Namespace("https://semanticpartners.com/data/test/")


class TestRunSpec:
    given_sub_pred_obj = """
    @prefix test-data: <https://semanticpartners.com/data/test/> .
    test-data:sub test-data:pred test-data:obj .
    """

    triple_store = {"type": MUST.rdfLib}

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

