from test.conftest import run_test_spec


def test_unit(unit_tests):
    assert run_test_spec(unit_tests)
    
def test_w3c(w3c_tests):
    assert run_test_spec(w3c_tests)