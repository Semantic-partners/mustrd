from mustrd.mustrdTestPlugin import run_test_spec

def test_unit(unit_tests):
    """Test implementation for .mustrd.ttl files"""
    # Store source mapping for VS Code test explorer
    if not hasattr(test_unit, 'source_mapping'):
        test_unit.source_mapping = {}

    # Get the source file for this test
    source_file = test_unit.source_mapping.get(unit_tests.id, None)
    if source_file:
        __tracebackhide__ = True
        # Set location for better test navigation
        test_unit.__source_file__ = source_file
        
    assert run_test_spec(unit_tests.unit_test)