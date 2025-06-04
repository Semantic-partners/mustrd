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
import pytest
from pathlib import Path
from mustrd.mustrdTestPlugin import MustrdTestPlugin
from mustrd.mustrd import SpecSkipped
import logging
log = logging.getLogger(__name__)


def run_mustrd(config_path: str, *args, md_path: str = None, secrets: str = None):
    mustrd_plugin = MustrdTestPlugin(md_path, Path(config_path), secrets)
    log.setLevel(logging.DEBUG)  # or logging.INFO, as desired
    pytest.main([*args, "--log-cli-level=DEBUG"], plugins=[mustrd_plugin])
    return mustrd_plugin


# test collection of all tests
def test_collection_full():
    mustrd_plugin = run_mustrd("test/test-mustrd-config/test_mustrd_simple.ttl", "--collect-only")
    path = "rdflib"

    # Get collected items
    items = mustrd_plugin.items
    collected_nodes = set(map(lambda item: item.name, items))
    skipped_nodes = set(map(lambda item: item.name,
                             # Filter on skipped items
                             list(filter(lambda item: isinstance(item.spec,
                                                                 SpecSkipped), items))))
    log.info(f"Collected nodes: {collected_nodes}")
    
    expected_collected = {
        "construct_spec_from_folders.mustrd.ttl",
        "construct_spec.mustrd.ttl",
        "construct_spec_mulitline_result.mustrd.ttl",
        "construct_spec_multiple_given_multile_then.mustrd.ttl",
        "construct_spec_variable.mustrd.ttl",
        "construct_spec_when_file_then_file.mustrd.ttl",
        "delete_data_spec.mustrd.ttl",
        "delete_insert_spec.mustrd.ttl",
        "delete_insert_spec_with_optional.mustrd.ttl",
        "delete_insert_spec_with_subselect.mustrd.ttl",
        "delete_spec.mustrd.ttl",
        "insert_data_spec.mustrd.ttl",
        "insert_spec.mustrd.ttl",
        "invalid_delete_insert_spec_with_table_result.mustrd.ttl",
        "invalid_delete_insert_with_inherited_given_and_empty_table_result.mustrd.ttl",
        "invalid_delete_insert_with_inherited_given_spec.mustrd.ttl",
        "invalid_select_spec_multiple_givens_for_inherited_state.mustrd.ttl",
        "invalid_select_spec_with_empty_graph_result.mustrd.ttl",
        "invalid_select_spec_with_statement_dataset_result.mustrd.ttl",
        "invalid_select_spec_with_table_dataset_given.mustrd.ttl",
        "invalid_spec.mustrd.ttl",
        "select_spec.mustrd.ttl",
        "select_spec_empty_result.mustrd.ttl",
        "select_spec_given_file.mustrd.ttl",
        "select_spec_given_file_then_file.mustrd.ttl",
        "select_spec_given_inherited_state.mustrd.ttl",
        "select_spec_multiline_result.mustrd.ttl",
        "select_spec_optional_result.mustrd.ttl",
        "select_spec_ordered.mustrd.ttl",
        "select_spec_variable.mustrd.ttl",
        "select_spec_variable_datatypes.mustrd.ttl",
        "spade_edn_group_source_then_file.mustrd.ttl",
    }

    expected_skipped = set()
    # we're changing bad config of a test spec so we fail, rather than skip it
    # expected_failed = {
    #     "invalid_delete_insert_spec_with_table_result.mustrd.ttl",
    #     "invalid_delete_insert_with_inherited_given_and_empty_table_result.mustrd.ttl",
    #     "invalid_delete_insert_with_inherited_given_spec.mustrd.ttl",
    #     "invalid_select_spec_multiple_givens_for_inherited_state.mustrd.ttl",
    #     "invalid_select_spec_with_empty_graph_result.mustrd.ttl",
    #     "invalid_select_spec_with_statement_dataset_result.mustrd.ttl",
    #     "invalid_select_spec_with_table_dataset_given.mustrd.ttl",
    #     "select_spec2.mustrd.ttl",
    # }

    expected_not_skipped = expected_collected - expected_skipped

    # Assert all expected collected nodes are present
    assert expected_collected <= collected_nodes, (
        f"Missing collected: {expected_collected - collected_nodes}\n"
        f"Unexpected collected: {collected_nodes - expected_collected}"
    )

    # Assert all expected skipped nodes are present in skipped_nodes
    assert expected_skipped <= skipped_nodes, (
        f"Missing skipped: {expected_skipped - skipped_nodes}\n"
        f"Unexpected skipped: {skipped_nodes - expected_skipped}"
    )

    # Assert that valid specs are not skipped
    assert not (expected_not_skipped & skipped_nodes), (
        f"Unexpectedly skipped: {expected_not_skipped & skipped_nodes}"
    )


def test_collection_path():
    path = "rdflib1"  # Use actual path where test files exist
    mustrd_plugin = run_mustrd("test/test-mustrd-config/test_mustrd_double.ttl",
                                "--collect-only", f"--pytest-path={path}")
    log.info(f"items: {mustrd_plugin.items}")
    
    # First verify we have items collected
    assert len(mustrd_plugin.items) > 0, "No items were collected"
    
    # Assert that all collected items are from the specified path
    for item in mustrd_plugin.items:
        assert path in str(item.spec.spec_source_file), f"Item {item.name} is not from path {path}"
    
    # Check for expected number of tests
    # Note: Adjust this number based on actual test files in the path
    expected_test_count = 32
    actual_test_count = len(mustrd_plugin.items)
    assert actual_test_count == expected_test_count, \
        f"Expected {expected_test_count} tests but found {actual_test_count}"

    # Optional: Verify specific test files are included
    test_names = set(item.name for item in mustrd_plugin.items)
    expected_names = {
        "construct_spec.mustrd.ttl",
        "select_spec.mustrd.ttl",
        # Add other expected test file names
    }
    assert expected_names.issubset(test_names), \
        f"Missing expected test files: {expected_names - test_names}"
    # Assert that we only collected tests from the specified path
    assert len(list(filter(lambda item: path not in item.name, mustrd_plugin.items))) == 0
    assert len(list(filter(lambda item: path in item.name, mustrd_plugin.items))) == 32


def test_collection_path3():
    path = "col1"
    mustrd_plugin = run_mustrd("test/test-mustrd-config/test_mustrd_complex.ttl",
                               "--collect-only", path)
    # Assert that we only collected tests from the specified path
    assert len(list(filter(lambda item: path not in item.name, mustrd_plugin.items))) == 0
    assert len(list(filter(lambda item: path in item.name, mustrd_plugin.items))) == 64



def test_run_spade_integration():
    path = "spade-integration"
    mustrd_plugin = run_mustrd("test/test-mustrd-config/test_mustrd_spade_integration.ttl", path)
    # Assert that we only collected tests from the specified path
    collected_names = set(item.name for item in mustrd_plugin.items)
    expected_names = {f"{path}/spade_edn_group_source_then_file.mustrd.ttl"}
    assert collected_names == expected_names



def test_mustrd_config_duplicate():
    # Mustrd test generation should fail with ValueError if configuration is not conform
    error = run_mustrd("test/test-mustrd-config/test_mustrd_error_duplicates.ttl", "--collect-only").collect_error
    shacl_report_graph = error.args[1]
    # report = shacl_report_graph.serialize(None, format="ttl")
    assert shacl_report_graph
    assert found_error_in_shacl_report(shacl_report_graph,
                                       "<https://mustrd.com/mustrdTest/test_unit>",
                                       "<https://mustrd.com/mustrdTest/hasSpecPath>",
                                       "<http://www.w3.org/ns/shacl#MaxCountConstraintComponent>")

    assert found_error_in_shacl_report(shacl_report_graph,
                                       "<https://mustrd.com/mustrdTest/test_unit>",
                                       "<https://mustrd.com/mustrdTest/hasDataPath>",
                                       "<http://www.w3.org/ns/shacl#MaxCountConstraintComponent>")

    assert found_error_in_shacl_report(shacl_report_graph,
                                       "<https://mustrd.com/mustrdTest/test_unit>",
                                       "<https://mustrd.com/mustrdTest/hasPytestPath>",
                                       "<http://www.w3.org/ns/shacl#MaxCountConstraintComponent>")


def test_mustrd_missing_props():
    # Mustrd test generation should fail with ValueError if configuration is not conform}
    error = run_mustrd("test/test-mustrd-config/test_mustrd_error_missing_prop.ttl", "--collect-only").collect_error
    shacl_report_graph = error.args[1]
    assert shacl_report_graph
    assert found_error_in_shacl_report(shacl_report_graph,
                                       "<https://mustrd.com/mustrdTest/test_unit>",
                                       "<https://mustrd.com/mustrdTest/hasSpecPath>",
                                       "<http://www.w3.org/ns/shacl#MinCountConstraintComponent>")

    assert found_error_in_shacl_report(shacl_report_graph,
                                       "<https://mustrd.com/mustrdTest/test_unit>",
                                       "<https://mustrd.com/mustrdTest/hasDataPath>",
                                       "<http://www.w3.org/ns/shacl#MinCountConstraintComponent>")

    # hasPytestPath has a default value, no value should be accepted
    assert not found_error_in_shacl_report(shacl_report_graph,
                                           "<https://mustrd.com/mustrdTest/test_unit>",
                                           "<https://mustrd.com/mustrdTest/hasPytestPath>",
                                           "<http://www.w3.org/ns/shacl#MinCountConstraintComponent>")

    #  has a default value, no value should be accepted
    assert not found_error_in_shacl_report(shacl_report_graph,
                                           "<https://mustrd.com/mustrdTest/test_unit>",
                                           "<https://mustrd.com/mustrdTest/filterOnTripleStore>",
                                           "<http://www.w3.org/ns/shacl#MinCountConstraintComponent>")


def test_triplestore_config():
    mustrd_plugin = run_mustrd("test/test-mustrd-config/test_mustrd_triplestore.ttl", "--collect-only")
    items = mustrd_plugin.items

    skipped_nodes = list(map(lambda item: item.name,
                             # Filter on skipped items
                             list(filter(lambda item: isinstance(item.spec,
                                                                 SpecSkipped), items))))
    failed_nodes = list(map(lambda item: item.name,
                             # Filter on skipped items
                             list(filter(lambda item: isinstance(item.spec,
                                                                 ValueError), items))))

    log.info(f"{skipped_nodes=}")
    log.info(f"{failed_nodes=}")
    assert has_item(skipped_nodes, "default.mustrd.ttl", "gdb")


# Returns true if a the report contains a node with the right constraint validation type on the path
def found_error_in_shacl_report(shacl_report_graph, node, path, constraint_type):
    return shacl_report_graph.query(f"""
                                    PREFIX : <https://mustrd.com/mustrdTest/>
                                    PREFIX sh: <http://www.w3.org/ns/shacl#>

                                    ASK {{
                                        [] a sh:ValidationReport ;
                                            sh:conforms false ;
                                            sh:result [
                                                a sh:ValidationResult ;
                                                sh:focusNode {node} ;
                                                sh:resultPath {path} ;
                                                sh:resultSeverity sh:Violation ;
                                                sh:sourceConstraintComponent {constraint_type} ;
                                            ]
                                    }}
                                    """).askAnswer


def has_item(node_ids: list, ttl_file: str, path: str):
    return f"{path}/{ttl_file}" in node_ids
