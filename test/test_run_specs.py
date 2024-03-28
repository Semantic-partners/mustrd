from mustrd.mustrdTestPlugin import run_test_spec


def test_unit_rdflib(unit_tests):
    assert run_test_spec(unit_tests)


def test_unit_gdb(unit_tests):
    assert run_test_spec(unit_tests)
