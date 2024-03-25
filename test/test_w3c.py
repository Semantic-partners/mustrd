from mustrd.mustrdTestPlugin import run_test_spec


def test_w3c_gdb(w3c_tests):
    assert run_test_spec(w3c_tests)
    
def test_w3c_rdflib(w3c_tests):
    assert run_test_spec(w3c_tests)