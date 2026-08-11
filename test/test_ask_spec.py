"""SPARQL ASK specs.

An ASK answers a boolean, so its `then` is a `must:AskResult` carrying that
boolean — there is no table or graph to compare. Expecting `false` is an
assertion in its own right: a spec that could only expect `true` would not be able
to tell "answered false" from "did not run".
"""

from rdflib import Graph, Namespace

from mustrd.mustrd import (
    AskSpecFailure,
    Specification,
    SpecInvalid,
    SpecPassed,
    check_result,
    run_spec,
)
from mustrd.mustrdRdfLib import execute_ask
from mustrd.namespace import MUST, TRIPLESTORE
from mustrd.spec_component import (
    AskThenSpec, ThenSpec, UpdatableDataset, parse_spec_component,
)

TEST_DATA = Namespace("https://semanticpartners.com/data/test/")
TRIPLE_STORE = {"type": TRIPLESTORE.RdfLib}

GIVEN = """
@prefix test-data: <https://semanticpartners.com/data/test/> .
test-data:sub test-data:pred test-data:obj .
"""

SPEC = """
@prefix must:      <https://mustrd.org/model/> .
@prefix test-data: <https://semanticpartners.com/data/test/> .

test-data:a_spec a must:TestSpec ;
    must:when [ a must:TextSparqlSource ;
                must:queryText "%(query)s" ;
                must:queryType must:AskSparql ] ;
    must:then [ a must:AskResult ; must:boolean %(expected)s ] .
"""


def a_given() -> UpdatableDataset:
    given = UpdatableDataset(default_union=True)
    given.default_graph.parse(data=GIVEN, format="ttl")
    return given


def spec_for(query: str, expected: str) -> Specification:
    spec_graph = Graph().parse(
        data=SPEC % {"query": query, "expected": expected}, format="ttl")
    when = parse_spec_component(
        subject=TEST_DATA.a_spec, predicate=MUST.when, spec_graph=spec_graph,
        run_config={}, mustrd_triple_store=TRIPLE_STORE)
    then = parse_spec_component(
        subject=TEST_DATA.a_spec, predicate=MUST.then, spec_graph=spec_graph,
        run_config={}, mustrd_triple_store=TRIPLE_STORE)
    return Specification(TEST_DATA.a_spec, TRIPLE_STORE, a_given(), when, then)


ASK_TRUE = ("PREFIX test-data: <https://semanticpartners.com/data/test/> "
            "ASK { test-data:sub test-data:pred test-data:obj }")
ASK_FALSE = ("PREFIX test-data: <https://semanticpartners.com/data/test/> "
             "ASK { test-data:sub test-data:pred test-data:nothing }")


# ---------------------------------------------------------------------------
# The executor
# ---------------------------------------------------------------------------
def test_the_executor_answers_true():
    assert execute_ask(TRIPLE_STORE, a_given(), ASK_TRUE) is True


def test_the_executor_answers_false():
    assert execute_ask(TRIPLE_STORE, a_given(), ASK_FALSE) is False


def test_the_executor_reads_a_named_graph():
    given = UpdatableDataset(default_union=True)
    given.get_context(TEST_DATA["graph-a"]).parse(data=GIVEN, format="ttl")

    query = ("PREFIX test-data: <https://semanticpartners.com/data/test/> "
             "ASK { GRAPH test-data:graph-a { ?s ?p ?o } }")

    assert execute_ask(TRIPLE_STORE, given, query) is True


# ---------------------------------------------------------------------------
# Parsing the then
# ---------------------------------------------------------------------------
def test_an_ask_result_parses_to_a_bool():
    spec = spec_for(ASK_TRUE, "true")

    assert isinstance(spec.then, AskThenSpec)
    assert spec.then.value is True


def test_expecting_false_parses_to_false_not_to_nothing():
    # `false` must survive as a value. Read as absence, an expected-false spec
    # would be indistinguishable from a spec with no expectation.
    spec = spec_for(ASK_FALSE, "false")

    assert spec.then.value is False


# ---------------------------------------------------------------------------
# End to end
# ---------------------------------------------------------------------------
def test_true_matching_true_passes():
    assert isinstance(run_spec(spec_for(ASK_TRUE, "true")), SpecPassed)


def test_false_matching_false_passes():
    assert isinstance(run_spec(spec_for(ASK_FALSE, "false")), SpecPassed)


def test_expecting_true_and_answering_false_fails():
    result = run_spec(spec_for(ASK_FALSE, "true"))

    assert isinstance(result, AskSpecFailure)
    assert result.expected is True
    assert result.actual is False


def test_expecting_false_and_answering_true_fails():
    result = run_spec(spec_for(ASK_TRUE, "false"))

    assert isinstance(result, AskSpecFailure)
    assert result.expected is False
    assert result.actual is True


def test_the_failure_says_both_booleans():
    lines = []
    from mustrd.mustrd import render_result_diff
    render_result_diff(run_spec(spec_for(ASK_FALSE, "true")), lines.append)

    assert any("answered False" in line and "expected True" in line for line in lines)


# ---------------------------------------------------------------------------
# Mismatched pairs. SHACL rejects these for a real spec; a Specification built
# directly still reaches check_result, which has to say so rather than fail deep
# inside rdflib's comparison of a bool against a graph.
# ---------------------------------------------------------------------------
def test_an_ask_with_a_graph_then_is_reported():
    then = ThenSpec()
    then.value = Graph()
    spec = spec_for(ASK_TRUE, "true")
    spec = Specification(
        spec.spec_uri, TRIPLE_STORE, a_given(), spec.when, then)

    result = run_spec(spec)

    assert isinstance(result, SpecInvalid)
    assert "must be a must:AskResult" in result.message


def test_an_ask_result_then_with_a_non_boolean_result_is_reported():
    then = AskThenSpec()
    then.value = True
    when = type("W", (), {"queryType": MUST.SelectSparql, "value": "SELECT * {}"})()
    spec = Specification(TEST_DATA.a_spec, TRIPLE_STORE, a_given(), [when], then)

    result = check_result(spec, "not a boolean")

    assert isinstance(result, SpecInvalid)
    assert "expects a boolean" in result.message


def test_a_given_is_untouched_by_an_ask():
    # An ASK reads. Nothing should be written, which matters when specs chain.
    given = a_given()
    before = len(given)

    execute_ask(TRIPLE_STORE, given, ASK_TRUE)

    assert len(given) == before
