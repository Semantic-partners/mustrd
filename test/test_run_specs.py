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

from rdflib import URIRef
from rdflib.namespace import Namespace

from mustrd import run_specs, SpecPassed, SpecSkipped, get_specs,review_results
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
            SpecSkipped(URIRef(TEST_DATA.a_complete_delete_insert_with_a_table_result_scenario), MUST.RdfLib, message="Incompatible result type for an update statement found in delete_insert_spec_with_table_result.ttl." ),
            SpecSkipped(URIRef(TEST_DATA.a_complete_delete_insert_with_inherited_given_and_empty_table_result_scenario), MUST.RdfLib, message="Attempted update on inherited state found in delete_insert_with_inherited_given_and_empty_table_result.ttl. Incompatible result type for an update statement found in delete_insert_with_inherited_given_and_empty_table_result.ttl." ),
            SpecSkipped(URIRef(TEST_DATA.a_complete_delete_insert_with_inherited_given_scenario), MUST.RdfLib, message="Attempted update on inherited state found in delete_insert_with_inherited_given_spec.ttl." ),
            SpecPassed(URIRef(TEST_DATA.a_complete_delete_insert_with_optional_scenario), MUST.RdfLib),
            SpecPassed(URIRef(TEST_DATA.a_complete_delete_insert_with_subselect_scenario), MUST.RdfLib),
            SpecPassed(URIRef(TEST_DATA.a_complete_delete_scenario), MUST.RdfLib),
            SpecPassed(URIRef(TEST_DATA.a_complete_insert_data_scenario), MUST.RdfLib),
            SpecPassed(URIRef(TEST_DATA.a_complete_insert_scenario), MUST.RdfLib),
            SpecSkipped(URIRef(TEST_DATA.a_complete_select_scenario), MUST.RdfLib, message="Duplicate subject URI found in select_spec2.ttl."),
            SpecPassed(URIRef(TEST_DATA.a_complete_select_scenario), MUST.RdfLib),
            SpecPassed(URIRef(TEST_DATA.a_complete_select_scenario_expected_empty_result), MUST.RdfLib),
            SpecPassed(URIRef(TEST_DATA.a_complete_select_scenario_given_file), MUST.RdfLib),
            SpecPassed(URIRef(TEST_DATA.a_complete_select_scenario_given_file_then_file), MUST.RdfLib),
            SpecSkipped(URIRef(TEST_DATA.a_complete_select_scenario_inherited_state), MUST.RdfLib, message="Unable to run Inherited State tests on Rdflib"),
            SpecPassed(URIRef(TEST_DATA.a_complete_select_scenario_multiline_result), MUST.RdfLib),
            SpecPassed(URIRef(TEST_DATA.a_complete_select_scenario_optional_result), MUST.RdfLib),
            SpecPassed(URIRef(TEST_DATA.a_complete_select_scenario_ordered), MUST.RdfLib),
            SpecPassed(URIRef(TEST_DATA.a_complete_select_scenario_variables_datatypes), MUST.RdfLib),
            SpecSkipped(URIRef(TEST_DATA.a_complete_select_scenario_with_empty_graph_result), MUST.RdfLib, message="Incompatible result type for a select statement found in select_spec_with_empty_graph_result.ttl."),
            SpecSkipped(URIRef(TEST_DATA.a_complete_select_scenario_with_statement_data_source_result), MUST.RdfLib, message="Incompatible result type for a select statement found in select_spec_with_statement_data_source_result.ttl."),
            SpecPassed(URIRef(TEST_DATA.a_complete_select_scenario_with_variables), MUST.RdfLib)
        ], f"TTL files in path: {list(test_spec_path.glob('**/*.ttl'))}"
