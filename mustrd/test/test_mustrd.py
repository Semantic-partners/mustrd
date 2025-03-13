from mustrd.mustrdTestPlugin import run_test_spec

# this is a weird function, to cause the mustrdTestPlugin to run the test
# it is not a normal test function
# ideally, we do not need this, but for now we do
def test_unit(unit_tests):
    assert run_test_spec(unit_tests.unit_test)
