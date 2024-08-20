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
from mustrd.mustrdTestPlugin import MustrdTestPlugin, parse_config
from mustrd.mustrd import SpecSkipped

from urllib.parse import urljoin
from rdflib.parser import _create_input_source_from_location
def run_mustrd(config_path: str, *args, md_path: str = None, secrets: str = None):
    test_config = parse_config(config_path)
    mustrd_plugin = MustrdTestPlugin(md_path, test_config, secrets )
    pytest.main([*args], plugins=[mustrd_plugin])
    return mustrd_plugin, test_config
    

# test collection of all tests
def test_collection_full():
    mustrd_plugin, test_config = run_mustrd("test/test-mustrd-config/test_mustrd_simple.ttl", "--collect-only")
    assert len(test_config) == 1
    pytest_path = test_config[0].pytest_path
    
    # Get collected items
    items = mustrd_plugin.items
    collected_nodes = list(map(lambda item: item.nodeid, items))
    skipped_nodes = list(map(lambda item: item.nodeid,  
                             # Filter on skipped items
                             list(filter(lambda item : isinstance(item.callspec.params["unit_tests"].unit_test, SpecSkipped), items))))
    
    # Check that the items have been collected
    assert has_item(collected_nodes, "construct_spec.mustrd.ttl", pytest_path)
    assert has_item(collected_nodes, "construct_spec_from_folders.mustrd.ttl", pytest_path)
    assert has_item(collected_nodes, "construct_spec_mulitline_result.mustrd.ttl", pytest_path)
    assert has_item(collected_nodes, "construct_spec_multiple_given_multile_then.mustrd.ttl", pytest_path)
    assert has_item(collected_nodes, "construct_spec_variable.mustrd.ttl", pytest_path)
    assert has_item(collected_nodes, "construct_spec_when_file_then_file.mustrd.ttl", pytest_path)
    assert has_item(collected_nodes, "delete_data_spec.mustrd.ttl", pytest_path)
    assert has_item(collected_nodes, "delete_insert_spec.mustrd.ttl", pytest_path)
    assert has_item(collected_nodes, "delete_insert_spec_with_optional.mustrd.ttl", pytest_path)
    assert has_item(collected_nodes, "delete_insert_spec_with_subselect.mustrd.ttl", pytest_path)
    assert has_item(collected_nodes, "delete_spec.mustrd.ttl", pytest_path)
    assert has_item(collected_nodes, "insert_data_spec.mustrd.ttl", pytest_path)
    assert has_item(collected_nodes, "insert_spec.mustrd.ttl", pytest_path)
    assert has_item(collected_nodes, "invalid_delete_insert_spec_with_table_result.mustrd.ttl", pytest_path)
    assert has_item(collected_nodes, "invalid_delete_insert_with_inherited_given_and_empty_table_result.mustrd.ttl", pytest_path)
    assert has_item(collected_nodes, "invalid_delete_insert_with_inherited_given_spec.mustrd.ttl", pytest_path)
    assert has_item(collected_nodes, "invalid_select_spec_multiple_givens_for_inherited_state.mustrd.ttl", pytest_path)
    assert has_item(collected_nodes, "invalid_select_spec_with_empty_graph_result.mustrd.ttl", pytest_path)
    assert has_item(collected_nodes, "invalid_select_spec_with_statement_dataset_result.mustrd.ttl", pytest_path)
    assert has_item(collected_nodes, "invalid_select_spec_with_table_dataset_given.mustrd.ttl", pytest_path)
    assert has_item(collected_nodes, "invalid_spec.mustrd.ttl", pytest_path)
    assert has_item(collected_nodes, "select_spec.mustrd.ttl", pytest_path)
    assert has_item(collected_nodes, "select_spec_empty_result.mustrd.ttl", pytest_path)
    assert has_item(collected_nodes, "select_spec_given_file.mustrd.ttl", pytest_path)
    assert has_item(collected_nodes, "select_spec_given_file_then_file.mustrd.ttl", pytest_path)
    assert has_item(collected_nodes, "select_spec_given_inherited_state.mustrd.ttl", pytest_path)
    assert has_item(collected_nodes, "select_spec_multiline_result.mustrd.ttl", pytest_path)
    assert has_item(collected_nodes, "select_spec_optional_result.mustrd.ttl", pytest_path)
    assert has_item(collected_nodes, "select_spec_ordered.mustrd.ttl", pytest_path)
    assert has_item(collected_nodes, "select_spec_variable.mustrd.ttl", pytest_path)
    assert has_item(collected_nodes, "select_spec_variable_datatypes.mustrd.ttl", pytest_path)
    assert has_item(collected_nodes, "select_spec2.mustrd.ttl", pytest_path)

    # Check that the valid specs are not skipped
    assert not has_item(skipped_nodes, "construct_spec.mustrd.ttl", pytest_path)
    assert not has_item(skipped_nodes, "construct_spec_mulitline_result.mustrd.ttl", pytest_path)
    assert not has_item(skipped_nodes, "construct_spec_multiple_given_multile_then.mustrd.ttl", pytest_path)
    assert not has_item(skipped_nodes, "construct_spec_variable.mustrd.ttl", pytest_path)
    assert not has_item(skipped_nodes, "construct_spec_when_file_then_file.mustrd.ttl", pytest_path)
    assert not has_item(skipped_nodes, "delete_data_spec.mustrd.ttl", pytest_path)
    assert not has_item(skipped_nodes, "delete_insert_spec.mustrd.ttl", pytest_path)
    assert not has_item(skipped_nodes, "delete_insert_spec_with_optional.mustrd.ttl", pytest_path)
    assert not has_item(skipped_nodes, "delete_insert_spec_with_subselect.mustrd.ttl", pytest_path)
    assert not has_item(skipped_nodes, "delete_spec.mustrd.ttl", pytest_path)
    assert not has_item(skipped_nodes, "insert_data_spec.mustrd.ttl", pytest_path)
    assert not has_item(skipped_nodes, "insert_spec.mustrd.ttl", pytest_path)
    assert not has_item(skipped_nodes, "select_spec.mustrd.ttl", pytest_path)
    assert not has_item(skipped_nodes, "select_spec_empty_result.mustrd.ttl", pytest_path)
    assert not has_item(skipped_nodes, "select_spec_given_file.mustrd.ttl", pytest_path)
    assert not has_item(skipped_nodes, "select_spec_given_file_then_file.mustrd.ttl", pytest_path)
    assert not has_item(skipped_nodes, "select_spec_given_inherited_state.mustrd.ttl", pytest_path)
    assert not has_item(skipped_nodes, "select_spec_multiline_result.mustrd.ttl", pytest_path)
    assert not has_item(skipped_nodes, "select_spec_optional_result.mustrd.ttl", pytest_path)
    assert not has_item(skipped_nodes, "select_spec_ordered.mustrd.ttl", pytest_path)
    assert not has_item(skipped_nodes, "select_spec_variable.mustrd.ttl", pytest_path)
    assert not has_item(skipped_nodes, "select_spec_variable_datatypes.mustrd.ttl", pytest_path)
    
    # Check invalid spec are skipped 
    assert has_item(skipped_nodes, "invalid_delete_insert_spec_with_table_result.mustrd.ttl", pytest_path)
    assert has_item(skipped_nodes, "invalid_delete_insert_with_inherited_given_and_empty_table_result.mustrd.ttl", pytest_path)
    assert has_item(skipped_nodes, "invalid_delete_insert_with_inherited_given_spec.mustrd.ttl", pytest_path)
    assert has_item(skipped_nodes, "invalid_select_spec_multiple_givens_for_inherited_state.mustrd.ttl", pytest_path)
    assert has_item(skipped_nodes, "invalid_select_spec_with_empty_graph_result.mustrd.ttl", pytest_path)
    assert has_item(skipped_nodes, "invalid_select_spec_with_statement_dataset_result.mustrd.ttl", pytest_path)
    assert has_item(skipped_nodes, "invalid_select_spec_with_table_dataset_given.mustrd.ttl", pytest_path)
    assert has_item(skipped_nodes, "select_spec2.mustrd.ttl", pytest_path)
    
    # FIXME: This is skipped is that normal?
    #assert has_item(skipped_nodes, "construct_spec_from_folders.mustrd.ttl", pytest_path)
    
    # FIXME: this should be skipped?
    #assert has_item(skipped_nodes, "invalid_spec.mustrd.ttl", pytest_path)
    
# Test that we collect one test if we give one nodeid
def test_collection_single():
    node_id = "mustrd/test/test_mustrd.py::test_unit[construct_spec.mustrd.ttl@rdflib]"
    mustrd_plugin, test_config = run_mustrd("test/test-mustrd-config/test_mustrd_simple.ttl", "--collect-only", node_id)
    items = mustrd_plugin.items
    assert list(map(lambda item: item.nodeid, items)) == ["mustrd/test/test_mustrd.py::test_unit[construct_spec.mustrd.ttl@rdflib]"]

def test_collection_path():
    path = "rdflib1"
    mustrd_plugin, test_config = run_mustrd("test/test-mustrd-config/test_mustrd_double.ttl", "--collect-only", path)
    # Assert that we only collected tests from the specified path
    assert len(list(filter(lambda item : path not in item.nodeid, mustrd_plugin.items))) == 0
    assert len(list(filter(lambda item : path in item.nodeid, mustrd_plugin.items))) == 32
    
def test_collection_path2():
    path = "col1/test1"
    mustrd_plugin, test_config = run_mustrd("test/test-mustrd-config/test_mustrd_complex.ttl", "--collect-only", path)
    # Assert that we only collected tests from the specified path
    assert len(list(filter(lambda item : path not in item.nodeid, mustrd_plugin.items))) == 0
    assert len(list(filter(lambda item : path in item.nodeid, mustrd_plugin.items))) == 32
    
def test_collection_path3():
    path = "col1"
    mustrd_plugin, test_config = run_mustrd("test/test-mustrd-config/test_mustrd_complex.ttl", "--collect-only", path)
    # Assert that we only collected tests from the specified path
    assert len(list(filter(lambda item : path not in item.nodeid, mustrd_plugin.items))) == 0
    assert len(list(filter(lambda item : path in item.nodeid, mustrd_plugin.items))) == 64
    
def test_mustrd_config_duplicate():
    # Mustrd test generation should fail with ValueError if configuration is not conform
    with pytest.raises(ValueError) as error:
        run_mustrd("test/test-mustrd-config/test_mustrd_error_duplicates.ttl", "--collect-only")
    assert error
    shacl_report_graph = error.value.args[1]
    #report = shacl_report_graph.serialize(None, format="ttl")
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
    # Mustrd test generation should fail with ValueError if configuration is not conform
    with pytest.raises(ValueError) as error:
        run_mustrd("test/test-mustrd-config/test_mustrd_error_missing_prop.ttl", "--collect-only")
    assert error
    shacl_report_graph = error.value.args[1]
    #report = shacl_report_graph.serialize(None, format="ttl")
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
    mustrd_plugin, config = run_mustrd("test/test-mustrd-config/test_mustrd_triplestore.ttl", "--collect-only")
    items = mustrd_plugin.items
    
    skipped_nodes = list(map(lambda item: item.nodeid,  
                             # Filter on skipped items
                             list(filter(lambda item : isinstance(item.callspec.params["unit_tests"].unit_test, SpecSkipped), items))))
    
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
    

def get_node_id(ttl_file: str, path: str):
    return f"mustrd/test/test_mustrd.py::test_unit[{ttl_file}@{path}]"

def has_item(node_ids: list, ttl_file: str, path: str):
    return get_node_id(ttl_file, path) in node_ids