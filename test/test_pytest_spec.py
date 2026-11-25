"""Specs written in code (mustrd.pytest_spec): the `spec` fixture and mustrd_spec.cq(...).

Runs a small suite of code specs through the plugin in a nested pytest run (as
test_coverage_plugin.py does), and checks the coverage and competency questions it reports.
"""
import pytest

from mustrd.mustrdTestPlugin import MustrdTestPlugin

ONTOLOGY = """
@prefix ex: <https://example.org/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
ex:Movie a owl:Class .
ex:title a owl:DatatypeProperty .
ex:runtime a owl:DatatypeProperty .
"""

CONFIG = """
@prefix : <https://mustrd.org/mustrdTest/> .
:specs a :MustrdTest ; :hasOntologyPath "ontology.ttl" ; :hasSpecPath "." ; :hasDataPath "." .
"""

SPECS = '''
import pytest

@pytest.fixture
def mustrd_spec_prefixes():
    return "@prefix ex: <https://example.org/> ."

def test_titles(mustrd_spec):
    mustrd_spec.cq("CQ-01", "What are the movie titles?")
    mustrd_spec.given('<https://example.org/m1> a ex:Movie ; ex:title "The Movie" .')
    mustrd_spec.when("SELECT ?title WHERE { ?movie a ex:Movie ; ex:title ?title }")
    mustrd_spec.then([("The Movie",)])

def test_runtimes_fails(mustrd_spec):
    mustrd_spec.cq("CQ-02", "How long is each movie?")
    mustrd_spec.given('<https://example.org/m1> a ex:Movie ; ex:runtime 100 .')
    mustrd_spec.when("SELECT ?runtime WHERE { ?movie ex:runtime ?runtime }")
    mustrd_spec.then([(99,)])
'''


def _run(tmp_path):
    (tmp_path / "ontology.ttl").write_text(ONTOLOGY)
    (tmp_path / "mustrd-config.ttl").write_text(CONFIG)
    (tmp_path / "test_code_specs.py").write_text(SPECS)
    md = tmp_path / "report.md"
    plugin = MustrdTestPlugin(str(md), tmp_path / "mustrd-config.ttl", None, term_coverage=True, cq=True)
    exit_code = pytest.main([str(tmp_path / "test_code_specs.py"), "-p", "no:cacheprovider"], plugins=[plugin])
    return exit_code, md.read_text(encoding="utf-8")


def test_code_specs_report_coverage_and_competency_questions(tmp_path):
    exit_code, text = _run(tmp_path)
    assert exit_code == pytest.ExitCode.TESTS_FAILED  # test_runtimes_fails fails, on purpose
    # Only the passing spec counts: ex:Movie and ex:title, not ex:runtime.
    assert "**Overall: 2/3 terms exercised by the tests = 67%**" in text
    # Both questions are listed without a CQ file, each linked to its test.
    assert "2 competency questions — 2 with a test, 0 without." in text
    assert "What are the movie titles?" in text and "test_titles" in text
    assert "How long is each movie?" in text and "test_runtimes_fails" in text
