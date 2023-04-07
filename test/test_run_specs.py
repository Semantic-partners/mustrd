from rdflib import URIRef
from rdflib.namespace import Namespace

from mustrd import run_specs, SpecPassed
from namespace import MUST
from src.utils import get_project_root

TEST_DATA = Namespace("https://semanticpartners.com/data/test/")


class TestRunSpecs:
    def test_find_specs_in_path_and_run_them(self):
        project_root = get_project_root()
        test_spec_path = project_root / "test" / "test-specs"
        results = run_specs(test_spec_path)
        results.sort(key=lambda sr: sr.spec_uri)
        assert results == [
            SpecPassed(URIRef(TEST_DATA.a_complete_construct_scenario), MUST.rdfLib),
            SpecPassed(URIRef(TEST_DATA.a_complete_construct_scenario_multiline_result), MUST.rdfLib),
            SpecPassed(URIRef(TEST_DATA.a_complete_construct_scenario_when_file), MUST.rdfLib),
            SpecPassed(URIRef(TEST_DATA.a_complete_construct_scenario_with_variables), MUST.rdfLib),
            SpecPassed(URIRef(TEST_DATA.a_complete_delete_data_scenario), MUST.rdfLib),
            SpecPassed(URIRef(TEST_DATA.a_complete_delete_insert_scenario), MUST.rdfLib),
            SpecPassed(URIRef(TEST_DATA.a_complete_delete_scenario), MUST.rdfLib),
            SpecPassed(URIRef(TEST_DATA.a_complete_insert_data_scenario), MUST.rdfLib),
            SpecPassed(URIRef(TEST_DATA.a_complete_insert_scenario), MUST.rdfLib),
            SpecPassed(URIRef(TEST_DATA.a_complete_select_scenario), MUST.rdfLib),
            SpecPassed(URIRef(TEST_DATA.a_complete_select_scenario_expected_empty_result), MUST.rdfLib),
            SpecPassed(URIRef(TEST_DATA.a_complete_select_scenario_given_file), MUST.rdfLib),
            SpecPassed(URIRef(TEST_DATA.a_complete_select_scenario_given_file_then_file), MUST.rdfLib),
            SpecPassed(URIRef(TEST_DATA.a_complete_select_scenario_multiline_result), MUST.rdfLib),
            SpecPassed(URIRef(TEST_DATA.a_complete_select_scenario_optional_result), MUST.rdfLib),
            SpecPassed(URIRef(TEST_DATA.a_complete_select_scenario_ordered), MUST.rdfLib),
            SpecPassed(URIRef(TEST_DATA.a_complete_select_scenario_variables_datatypes), MUST.rdfLib),
            SpecPassed(URIRef(TEST_DATA.a_complete_select_scenario_with_variables), MUST.rdfLib)
        ], f"TTL files in path: {list(test_spec_path.glob('**/*.ttl'))}"
