from rdflib import URIRef
from rdflib.namespace import Namespace

from mustrd import run_specs, SpecPassed, TestSkipped, get_specs,review_results
from namespace import MUST
from src.utils import get_project_root

TEST_DATA = Namespace("https://semanticpartners.com/data/test/")


class TestRunSpecs:
    def test_find_specs_in_path_and_run_them(self):
        project_root = get_project_root()
        test_spec_path = project_root / "test" / "test-specs"
        folder = project_root / "test" / "data"
        verbose = False
        triple_stores = [{'type': MUST.RdfLib}]
        spec_uris, spec_graph, results = get_specs(test_spec_path, triple_stores)

        final_results = run_specs( spec_uris, spec_graph, results, triple_stores, folder, folder, folder)
        review_results(final_results, verbose)
        results.sort(key=lambda sr: sr.spec_uri)
        assert results == [
            SpecPassed(URIRef(TEST_DATA.a_complete_construct_scenario), MUST.RdfLib),
            SpecPassed(URIRef(TEST_DATA.a_complete_construct_scenario_from_folders), MUST.RdfLib),
            SpecPassed(URIRef(TEST_DATA.a_complete_construct_scenario_multiline_result), MUST.RdfLib),
            SpecPassed(URIRef(TEST_DATA.a_complete_construct_scenario_multiple_given_multiple_then), MUST.RdfLib),
            SpecPassed(URIRef(TEST_DATA.a_complete_construct_scenario_when_file_then_file), MUST.RdfLib),
            SpecPassed(URIRef(TEST_DATA.a_complete_construct_scenario_with_variables), MUST.RdfLib),
            SpecPassed(URIRef(TEST_DATA.a_complete_delete_data_scenario), MUST.RdfLib),
            SpecPassed(URIRef(TEST_DATA.a_complete_delete_insert_scenario), MUST.RdfLib),
            TestSkipped(URIRef(TEST_DATA.a_complete_delete_insert_with_inherited_given_scenario), MUST.RdfLib, message="Attempted update on inherited state. delete_insert_with_inherited_given_spec.ttl. Test skipped" ),
            SpecPassed(URIRef(TEST_DATA.a_complete_delete_insert_with_optional_scenario), MUST.RdfLib),
            SpecPassed(URIRef(TEST_DATA.a_complete_delete_insert_with_subselect_scenario), MUST.RdfLib),
            SpecPassed(URIRef(TEST_DATA.a_complete_delete_scenario), MUST.RdfLib),
            SpecPassed(URIRef(TEST_DATA.a_complete_insert_data_scenario), MUST.RdfLib),
            SpecPassed(URIRef(TEST_DATA.a_complete_insert_scenario), MUST.RdfLib),
            SpecPassed(URIRef(TEST_DATA.a_complete_select_scenario), MUST.RdfLib),
            SpecPassed(URIRef(TEST_DATA.a_complete_select_scenario_expected_empty_result), MUST.RdfLib),
            SpecPassed(URIRef(TEST_DATA.a_complete_select_scenario_given_file), MUST.RdfLib),
            SpecPassed(URIRef(TEST_DATA.a_complete_select_scenario_given_file_then_file), MUST.RdfLib),
            SpecPassed(URIRef(TEST_DATA.a_complete_select_scenario_inherited_state), MUST.RdfLib) ,
            SpecPassed(URIRef(TEST_DATA.a_complete_select_scenario_multiline_result), MUST.RdfLib),
            SpecPassed(URIRef(TEST_DATA.a_complete_select_scenario_optional_result), MUST.RdfLib),
            SpecPassed(URIRef(TEST_DATA.a_complete_select_scenario_ordered), MUST.RdfLib),
            SpecPassed(URIRef(TEST_DATA.a_complete_select_scenario_variables_datatypes), MUST.RdfLib),
            SpecPassed(URIRef(TEST_DATA.a_complete_select_scenario_with_variables), MUST.RdfLib)
        ], f"TTL files in path: {list(test_spec_path.glob('**/*.ttl'))}"
