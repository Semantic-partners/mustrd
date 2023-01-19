from rdflib.namespace import Namespace
from namespace import MUST
from mustrdRdfLib import MustrdRdfLib
from rdflib import Graph

from mustrd import  SpecPassed, execute_when, Spec_component, ConstructSpecFailure
from graph_util import graph_comparison_message
from rdflib.compare import isomorphic


TEST_DATA = Namespace("https://semanticpartners.com/data/test/")


class TestRunConstructSpec:
    def test_construct_spec_passes(self):
        given =Spec_component()
        when = Spec_component()
        then = Spec_component()

        given.value = "<https://semanticpartners.com/data/test/sub> <https://semanticpartners.com/data/test/pred> <https://semanticpartners.com/data/test/obj> ."

        when.value = "CONSTRUCT {?s ?p ?o} WHERE { ?s ?p ?o }"
        when.queryType = MUST.ConstructSparql

        then.value = "<https://semanticpartners.com/data/test/sub> <https://semanticpartners.com/data/test/pred> <https://semanticpartners.com/data/test/obj> ."
        spec_uri = TEST_DATA.my_first_spec

        actual_status = execute_when(when, given, then, spec_uri, MustrdRdfLib())

        assert actual_status == SpecPassed(spec_uri)

    def test_construct_spec_fails_with_graph_comparison(self):
        given =Spec_component()
        when = Spec_component()
        then = Spec_component()

        given.value = "<https://semanticpartners.com/data/test/sub> <https://semanticpartners.com/data/test/pred> <https://semanticpartners.com/data/test/obj> ."

        when.value = "CONSTRUCT {?s ?p ?o} WHERE { ?s ?p ?o }"
        when.queryType = MUST.ConstructSparql

        then.value = "<https://semanticpartners.com/data/test/obj> <https://semanticpartners.com/data/test/sub> <https://semanticpartners.com/data/test/pred> ."
        spec_uri = TEST_DATA.my_first_spec

        expected_in_expected_not_in_actual = Graph()
        expected_in_expected_not_in_actual.add((TEST_DATA.obj, TEST_DATA.sub, TEST_DATA.pred))

        expected_in_actual_not_in_expected = Graph()
        expected_in_actual_not_in_expected.add((TEST_DATA.sub, TEST_DATA.pred, TEST_DATA.obj))

        actual_status = execute_when(when, given, then, spec_uri, MustrdRdfLib())

        assert type(actual_status) == ConstructSpecFailure
        graph_comparison = actual_status.graph_comparison
        assert isomorphic(graph_comparison.in_expected_not_in_actual, expected_in_expected_not_in_actual), graph_comparison_message(expected_in_expected_not_in_actual, graph_comparison.in_expected_not_in_actual)
        assert isomorphic(graph_comparison.in_actual_not_in_expected, expected_in_actual_not_in_expected), graph_comparison_message(expected_in_actual_not_in_expected, graph_comparison.in_actual_not_in_expected)
        assert len(graph_comparison.in_both.all_nodes()) == 0