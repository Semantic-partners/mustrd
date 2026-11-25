"""Specs in code for test_pytest_spec.py. Not named test_*.py, so only that test runs them:
test_runtimes_fails fails on purpose."""
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
