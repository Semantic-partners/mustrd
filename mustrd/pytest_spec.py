"""Specs written in code, as pytest tests.

A spec checks that a SPARQL query gives the expected answer on some test data:

    def test_cq_01_movie_titles(mustrd_spec):
        mustrd_spec.cq("CQ-01", "What are the movie titles?")   # optional: link a competency question
        mustrd_spec.given('<movie/1> a ex:Movie ; ex:title "The Movie" .')
        mustrd_spec.when("SELECT ?title WHERE { ?movie a ex:Movie ; ex:title ?title }")
        mustrd_spec.then([("The Movie",)])

The test runs once, in the normal pytest run. With --mustrd, the plugin counts its data and
query towards the ontology coverage report, but only when the test passes, and lists its
competency question in the report. Without --mustrd, it is a plain pytest test.

Prefixes for the Turtle and the SPARQL come from the `mustrd_spec_prefixes` fixture. Override it in
your conftest.py:

    @pytest.fixture
    def mustrd_spec_prefixes():
        return "@prefix ex: <https://example.org/> ."
"""
import textwrap
from types import SimpleNamespace
from urllib.parse import quote

import pytest
from rdflib import Graph


class Spec:
    def __init__(self, record: SimpleNamespace, prefixes: str):
        self.record = record  # what the plugin reads at the end of the run (see the `mustrd_spec` fixture)
        self.prefixes = prefixes
        self.data = None
        self.result = None

    def cq(self, cq_id: str, question: str) -> None:
        """Link this test to a competency question in the report. Call it first in the test,
        so the question is listed (as failing) even when a later step fails."""
        self.record.competency_questions[cq_id] = question

    def given(self, turtle: str) -> None:
        """Set the test data, written in Turtle."""
        self.data = Graph().parse(data=self.prefixes + textwrap.dedent(turtle), format="turtle")
        self.record.given = self.data

    def when(self, sparql: str):
        """Run a SPARQL query on the test data and return its result."""
        assert self.data is not None, "Set the test data with mustrd_spec.given(...) before mustrd_spec.when(...)"
        # The data knows its prefixes, so the query doesn't have to declare them.
        self.result = self.data.query(sparql)
        # The report parses the query on its own, so declare the prefixes it uses.
        prefixes = "".join(
            f"PREFIX {prefix}: <{namespace}>\n"
            for prefix, namespace in self.data.namespaces()
            if f"{prefix}:" in sparql
        )
        # Remove the test's indentation, so the query lines up with the prefixes in the report.
        self.record.when.append(SimpleNamespace(value=prefixes + textwrap.dedent(sparql).strip()))
        return self.result

    def then(self, expected: list) -> None:
        """Check that the last query returned exactly these rows, in this order."""
        assert self.result is not None, "Ask the question with mustrd_spec.when(...) before mustrd_spec.then(...)"
        rows = [tuple(value.toPython() for value in row) for row in self.result]
        assert rows == expected


def spec_uri(nodeid: str) -> str:
    """An IRI for a test, which links it to its competency question in the report."""
    return f"urn:pytest:{quote(nodeid, safe='')}"


@pytest.fixture
def mustrd_spec_prefixes() -> str:
    """Turtle prefixes for mustrd_spec.given(...). Override this fixture in your conftest.py."""
    return ""


@pytest.fixture
def mustrd_spec(request, mustrd_spec_prefixes) -> Spec:
    """A spec written in code. See the module docstring."""
    test = request.node
    # The plugin reports on every test that has a `spec` with these fields (as its own specs do),
    # plus `competency_questions`, filled in by mustrd_spec.cq(...).
    test.spec = SimpleNamespace(
        spec_uri=spec_uri(test.nodeid),
        spec_file_name=test.name,
        spec_source_file=str(test.path),
        given=Graph(),
        when=[],
        competency_questions={},
    )
    return Spec(test.spec, mustrd_spec_prefixes)
