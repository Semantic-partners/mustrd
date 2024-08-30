from mustrd.mustrdTestPlugin import run_test_spec


def test_unit(unit_tests):
    assert run_test_spec(unit_tests.unit_test)
