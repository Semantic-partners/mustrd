import pytest
from pathlib import Path
from mustrd.mustrdTestPlugin import MustrdTestPlugin
from mustrd.mustrd import SpecInvalid
import logging
from pyshacl import validate

log = logging.getLogger(__name__)


def run_mustrd(config_path: str, *args, md_path: str = None, secrets: str = None):
    mustrd_plugin = MustrdTestPlugin(md_path, Path(config_path), secrets)
    log.setLevel(logging.DEBUG)  # or logging.INFO, as desired
    pytest.main([*args, "--log-cli-level=DEBUG"], plugins=[mustrd_plugin])
    return mustrd_plugin


# test collection of all tests
def test_collection_full():
    mustrd_plugin = run_mustrd(
        "test/test-mustrd-config/test_mustrd_simple.ttl", "--collect-only"
    )
    path = "rdflib"

    # Get collected items
    items = mustrd_plugin.items
    collected_nodes = set(map(lambda item: item.name, items))
    invalid_nodes = set(
        map(
            lambda item: item.name,
            # Filter on invalid items
            list(filter(lambda item: isinstance(item.spec, SpecInvalid), items)),
        )
    )
    log.info(f"Collected nodes: {collected_nodes}")

    expected_collected = {
        "construct_spec_from_folders.mustrd.ttl",
        "construct_spec.mustrd.ttl",
        "construct_spec_mulitline_result.mustrd.ttl",
        "construct_spec_multiple_given_multile_then.mustrd.ttl",
        "construct_spec_variable.mustrd.ttl",
        "construct_spec_when_file_then_file.mustrd.ttl",
        "construct_spec_when_file_then_file_as_uris.mustrd.ttl",
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
        "spade_edn_group_source_with_two_steps_then_file.mustrd.ttl"
    }

    expected_invalid = {
        "invalid_spec.mustrd.ttl",
        'invalid_select_spec_multiple_givens_for_inherited_state.mustrd.ttl',
        'invalid_select_spec_with_statement_dataset_result.mustrd.ttl',
        'invalid_delete_insert_spec_with_table_result.mustrd.ttl',
        'invalid_delete_insert_with_inherited_given_and_empty_table_result.mustrd.ttl',
        'invalid_select_spec_with_table_dataset_given.mustrd.ttl',
        'invalid_select_spec_with_empty_graph_result.mustrd.ttl',
        'invalid_delete_insert_with_inherited_given_spec.mustrd.ttl',
    }

    expected_not_invalid = expected_collected - expected_invalid

    # Assert all expected collected nodes are present
    assert expected_collected <= collected_nodes, (
        f"Missing collected: {expected_collected - collected_nodes}\n"
        f"Unexpected collected: {collected_nodes - expected_collected}"
    )
    # Assert all expected invalid nodes are present in invalid_nodes
    assert expected_invalid <= invalid_nodes, (
        f"Missing invalid: {expected_invalid - invalid_nodes}\n"
        f"Unexpected invalid: {invalid_nodes - expected_invalid}"
    )

    # Assert that valid specs are not marked as invalid
    assert not (
        expected_not_invalid & invalid_nodes
    ), f"Unexpectedly invalid: {expected_not_invalid & invalid_nodes}"


def test_collection_path():
    path = "rdflib1"
    mustrd_plugin = run_mustrd(
        "test/test-mustrd-config/test_mustrd_double.ttl",
        "--collect-only",
        f"--pytest-path={path}",
    )

    item_names = set([item.name for item in mustrd_plugin.items])
    logging.info(f"Collected item names: {item_names}")
    expected_item_names = {
        "delete_spec.mustrd.ttl",
        "insert_spec.mustrd.ttl",
        "delete_insert_spec_with_optional.mustrd.ttl",
        "select_spec_variable.mustrd.ttl",
        "construct_spec_from_folders.mustrd.ttl",
        "delete_insert_spec.mustrd.ttl",
        "delete_insert_spec_with_subselect.mustrd.ttl",
        "select_spec_multiline_result.mustrd.ttl",
        "select_spec_given_file_then_file.mustrd.ttl",
        "construct_spec_when_file_then_file.mustrd.ttl",
        "select_spec_given_file.mustrd.ttl",
        "construct_spec_when_file_then_file_as_uris.mustrd.ttl",
        "spade_edn_group_source_then_file.mustrd.ttl",
        "select_spec_ordered.mustrd.ttl",
        "select_spec.mustrd.ttl",
        "construct_spec_multiple_given_multile_then.mustrd.ttl",
        "insert_data_spec.mustrd.ttl",
        "select_spec_optional_result.mustrd.ttl",
        "delete_data_spec.mustrd.ttl",
        "spade_edn_group_source_then_file.mustrd.ttl",
        "spade_edn_group_source_with_two_steps_then_file.mustrd.ttl",
        "select_spec_empty_result.mustrd.ttl",
        "select_spec_variable_datatypes.mustrd.ttl",
        "construct_spec.mustrd.ttl",
        "construct_spec_mulitline_result.mustrd.ttl",
        "construct_spec_variable.mustrd.ttl",
    }
    assert item_names == expected_item_names, (
        f"Expected item names: {expected_item_names}\n"
        f"Actual item names: {item_names}"
    )


def test_collection_pytest_path_is_a_startsWithCheck():
    path = "col1/test1"
    mustrd_plugin = run_mustrd(
        "test/test-mustrd-config/test_mustrd_complex.ttl",
        "--collect-only",
        f"--pytest-path={path}",
    )

    item_names = sorted([item.name for item in mustrd_plugin.items])
    logging.info(f"expected_item_names = {item_names}")
    expected_item_names = [
        "construct_spec.mustrd.ttl",
        "construct_spec_from_folders.mustrd.ttl",
        "construct_spec_mulitline_result.mustrd.ttl",
        "construct_spec_multiple_given_multile_then.mustrd.ttl",
        "construct_spec_variable.mustrd.ttl",
        "construct_spec_when_file_then_file.mustrd.ttl",
        "construct_spec_when_file_then_file_as_uris.mustrd.ttl",
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
        'spade_edn_group_source_with_two_steps_then_file.mustrd.ttl'
    ]
    # Assert that we only collected tests from the specified path
    assert item_names == expected_item_names, (
        f"Expected item names: {expected_item_names}\n"
        f"Actual item names: {item_names}"
    )


def test_collection_pytest_path_is_a_startsWithCheck_across_multiple_mustrdsuites():
    path = "col1"
    mustrd_plugin = run_mustrd(
        "test/test-mustrd-config/test_mustrd_complex.ttl",
        "--collect-only",
        f"--pytest-path={path}",
    )

    item_names = sorted({item.name for item in mustrd_plugin.items})
    logging.info(f"expected_item_names = {item_names}")
    expected_item_names = [
        "construct_spec.mustrd.ttl",
        "construct_spec_from_folders.mustrd.ttl",
        "construct_spec_mulitline_result.mustrd.ttl",
        "construct_spec_multiple_given_multile_then.mustrd.ttl",
        "construct_spec_variable.mustrd.ttl",
        "construct_spec_when_file_then_file.mustrd.ttl",
        "construct_spec_when_file_then_file_as_uris.mustrd.ttl",
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
        'spade_edn_group_source_with_two_steps_then_file.mustrd.ttl'
    ]
    assert item_names == expected_item_names, (
        f"Expected item names: {expected_item_names}\n"
        f"Actual item names: {item_names}"
    )


@pytest.mark.skip(reason="Integration test for spade, NOT READY YET")
def test_run_spade_integration():
    path = "spade-integration"
    mustrd_plugin = run_mustrd(
        "test/test-mustrd-config/test_mustrd_spade_integration.ttl",
        f"--pytest-path={path}",
    )
    # Assert that we only collected tests from the specified path
    collected_names = set(item.name for item in mustrd_plugin.items)
    expected_names = {f"spade_edn_group_source_then_file.mustrd.ttl"}
    assert collected_names == expected_names


def test_mustrd_config_duplicate_should_fail_shacl_tests():
    # Mustrd test generation should fail with ValueError if configuration does not conform to the SHACL schema
    error = run_mustrd(
        "test/test-mustrd-config/test_mustrd_error_duplicates.ttl", "--collect-only"
    ).collect_error
    shacl_report_graph = error.args[1]
    # report = shacl_report_graph.serialize(None, format="ttl")
    assert shacl_report_graph, "SHACL report graph should not be empty"
    assert found_error_in_shacl_report(
        shacl_report_graph,
        "<https://mustrd.org/mustrdTest/test_unit>",
        "<https://mustrd.org/mustrdTest/hasSpecPath>",
        "<http://www.w3.org/ns/shacl#MaxCountConstraintComponent>",
    ), shacl_report_graph.serialize(format="ttl")

    assert found_error_in_shacl_report(
        shacl_report_graph,
        "<https://mustrd.org/mustrdTest/test_unit>",
        "<https://mustrd.org/mustrdTest/hasDataPath>",
        "<http://www.w3.org/ns/shacl#MaxCountConstraintComponent>",
    )

    assert found_error_in_shacl_report(
        shacl_report_graph,
        "<https://mustrd.org/mustrdTest/test_unit>",
        "<https://mustrd.org/mustrdTest/hasPytestPath>",
        "<http://www.w3.org/ns/shacl#MaxCountConstraintComponent>",
    )


def test_mustrd_missing_props():
    # Mustrd test generation should fail with ValueError if configuration is not conform}
    error = run_mustrd(
        "test/test-mustrd-config/test_mustrd_error_missing_prop.ttl", "--collect-only"
    ).collect_error
    shacl_report_graph = error.args[1]
    assert shacl_report_graph
    assert found_error_in_shacl_report(
        shacl_report_graph,
        "<https://mustrd.org/mustrdTest/test_unit>",
        "<https://mustrd.org/mustrdTest/hasSpecPath>",
        "<http://www.w3.org/ns/shacl#MinCountConstraintComponent>",
    )

    assert found_error_in_shacl_report(
        shacl_report_graph,
        "<https://mustrd.org/mustrdTest/test_unit>",
        "<https://mustrd.org/mustrdTest/hasDataPath>",
        "<http://www.w3.org/ns/shacl#MinCountConstraintComponent>",
    )

    # hasPytestPath has a default value, no value should be accepted
    assert not found_error_in_shacl_report(
        shacl_report_graph,
        "<https://mustrd.org/mustrdTest/test_unit>",
        "<https://mustrd.org/mustrdTest/hasPytestPath>",
        "<http://www.w3.org/ns/shacl#MinCountConstraintComponent>",
    )

    #  has a default value, no value should be accepted
    assert not found_error_in_shacl_report(
        shacl_report_graph,
        "<https://mustrd.org/mustrdTest/test_unit>",
        "<https://mustrd.org/mustrdTest/filterOnTripleStore>",
        "<http://www.w3.org/ns/shacl#MinCountConstraintComponent>",
    )


@pytest.mark.skip(
    reason="Not clear what this was trying to test. Looks like it's expect the graphdb tests to be skipped, but they are not."
)
def test_triplestore_config():
    mustrd_plugin = run_mustrd(
        "test/test-mustrd-config/test_mustrd_triplestore.ttl", "--collect-only"
    )
    items = mustrd_plugin.items
    errors = getattr(mustrd_plugin, "collect_error", None)
    log.info(f"Errors: {errors}")
    invalid_nodes = list(
        map(
            lambda item: item.name,
            # Filter on invalid items
            list(filter(lambda item: isinstance(item.spec, SpecInvalid), items)),
        )
    )
    failed_nodes = list(
        map(
            lambda item: item.name,
            # Filter on invalid items
            list(filter(lambda item: isinstance(item.spec, ValueError), items)),
        )
    )

    log.info(f"{invalid_nodes=}")
    log.info(f"{failed_nodes=}")
    assert has_item(invalid_nodes, "default.mustrd.ttl", "gdb")


# Returns true if a the report contains a node with the right constraint validation type on the path
def found_error_in_shacl_report(shacl_report_graph, node, path, constraint_type):
    return shacl_report_graph.query(
        f"""
                                    PREFIX : <https://mustrd.org/mustrdTest/>
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
                                    """
    ).askAnswer


def has_item(node_ids: list, ttl_file: str, path: str):
    return f"{path}/{ttl_file}" in node_ids
