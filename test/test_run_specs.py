from rdflib import URIRef
from rdflib.namespace import Namespace

from mustrd import run_specs, SpecPassed
from src.utils import get_project_root

TEST_DATA = Namespace("https://semanticpartners.com/data/test/")


class TestRunSpecs:
    def test_find_specs_in_path_and_run_them(self):
        project_root = get_project_root()
        test_spec_path = project_root / "test" / "test-specs"

        results = run_specs(test_spec_path)
        results.sort(key=lambda sr: sr.spec_uri)
        assert results == [
            SpecPassed(URIRef(TEST_DATA.a_complete_construct_scenario)),
            SpecPassed(URIRef(TEST_DATA.a_complete_construct_scenario_multiline_result)),
            SpecPassed(URIRef(TEST_DATA.a_complete_construct_scenario_when_file)),
            SpecPassed(URIRef(TEST_DATA.a_complete_construct_scenario_with_variables)),
            SpecPassed(URIRef(TEST_DATA.a_complete_delete_data_scenario)),
            SpecPassed(URIRef(TEST_DATA.a_complete_delete_insert_scenario)),
            SpecPassed(URIRef(TEST_DATA.a_complete_delete_scenario)),
            SpecPassed(URIRef(TEST_DATA.a_complete_insert_data_scenario)),
            SpecPassed(URIRef(TEST_DATA.a_complete_insert_scenario)),
            SpecPassed(URIRef(TEST_DATA.a_complete_select_scenario)),
            SpecPassed(URIRef(TEST_DATA.a_complete_select_scenario_expected_empty_result)),
            SpecPassed(URIRef(TEST_DATA.a_complete_select_scenario_given_file)),
            SpecPassed(URIRef(TEST_DATA.a_complete_select_scenario_given_file_then_file)),
            SpecPassed(URIRef(TEST_DATA.a_complete_select_scenario_multiline_result)),
            SpecPassed(URIRef(TEST_DATA.a_complete_select_scenario_optional_result)),
            SpecPassed(URIRef(TEST_DATA.a_complete_select_scenario_ordered)),
            SpecPassed(URIRef(TEST_DATA.a_complete_select_scenario_variables_datatypes)),
            SpecPassed(URIRef(TEST_DATA.a_complete_select_scenario_with_variables))
        ], f"TTL files in path: {list(test_spec_path.glob('**/*.ttl'))}"
