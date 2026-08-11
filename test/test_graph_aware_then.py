"""`must:matchNamedGraphs` — opt-in graph-by-graph comparison of a `then`.

You should not have to say which graph a triple is in just to assert that it
exists, so the default is unchanged: a `then` is compared as one flat union, even
when it is written as quads. Say `must:matchNamedGraphs true` and the layout
becomes part of the assertion — the same triples in the wrong graphs is a failure.

The pair of fixtures under test/data is the whole point: expected-named-graphs.trig
and expected-graphs-shuffled.trig hold the SAME triples in DIFFERENT graphs. A flat
comparison cannot tell them apart. A graph-aware one can.
"""

from pathlib import Path

import pytest
from rdflib import Dataset, Graph, Literal, Namespace

from mustrd.mustrd import (
    Specification,
    SpecPassed,
    UpdateSpecFailure,
    check_result,
    graphs_by_name,
)
from mustrd.namespace import MUST, TRIPLESTORE
from mustrd.spec_component import (
    GivenSpec, ThenSpec, UpdatableDataset, load_dataset_from_file,
    parse_spec_component,
)

TEST_DATA = Namespace("https://semanticpartners.com/data/test/")
TRIPLE_STORE = {"type": TRIPLESTORE.RdfLib}
DATA = Path(__file__).parent / "data"

CORRECT = DATA / "expected-named-graphs.trig"
SHUFFLED = DATA / "expected-graphs-shuffled.trig"

SPEC = """
@prefix must:      <https://mustrd.org/model/> .
@prefix test-data: <https://semanticpartners.com/data/test/> .

test-data:a_spec a must:TestSpec ;
    must:then [ a must:FileDataset ;
                %(flag)s
                must:file "%(file)s" ] .
"""


def then_from(path: Path, match_named_graphs: bool) -> ThenSpec:
    """Parse a `then` the way a real spec does, via the spec graph."""
    flag = "must:matchNamedGraphs true ;" if match_named_graphs else ""
    spec_graph = Graph().parse(
        data=SPEC % {"flag": flag, "file": path.name}, format="ttl")
    spec_graph.add((TEST_DATA.a_spec, MUST.specSourceFile,
                    Literal(str(DATA / "spec.mustrd.ttl"))))
    return parse_spec_component(
        subject=TEST_DATA.a_spec, predicate=MUST.then, spec_graph=spec_graph,
        run_config={"data_path": DATA}, mustrd_triple_store=TRIPLE_STORE)


def update_spec(then: ThenSpec) -> Specification:
    when = type("W", (), {"queryType": MUST.UpdateSparql, "value": "INSERT DATA {}"})()
    # UpdatableDataset, as a real given always is — a plain Dataset reprs via
    # rdflib's deprecated `identifier`, which the suite treats as an error.
    return Specification(
        TEST_DATA.a_spec, TRIPLE_STORE, UpdatableDataset(), [when], then)


# --------------------------------------------------------------------------
# Parsing the flag
# --------------------------------------------------------------------------
def test_a_then_is_flat_by_default():
    then = then_from(CORRECT, match_named_graphs=False)

    assert then.match_named_graphs is False
    assert not isinstance(then.value, Dataset)


def test_the_flag_keeps_the_named_graphs():
    then = then_from(CORRECT, match_named_graphs=True)

    assert then.match_named_graphs is True
    assert isinstance(then.value, Dataset)
    assert {str(g.identifier) for g in then.value.graphs()} >= {
        str(TEST_DATA["graph-a"]), str(TEST_DATA["graph-b"])}


# --------------------------------------------------------------------------
# What the flag changes
# --------------------------------------------------------------------------
def test_the_shuffled_layout_passes_flat():
    # The default. Same triples, different graphs — a flat union cannot tell.
    then = then_from(SHUFFLED, match_named_graphs=False)
    actual = load_dataset_from_file(CORRECT, GivenSpec()).value

    assert isinstance(check_result(update_spec(then), actual), SpecPassed)


def test_the_shuffled_layout_fails_graph_aware():
    # The point of the flag. Nothing else about the spec changed.
    then = then_from(SHUFFLED, match_named_graphs=True)
    actual = load_dataset_from_file(CORRECT, GivenSpec()).value

    result = check_result(update_spec(then), actual)

    assert isinstance(result, UpdateSpecFailure)


def test_the_correct_layout_passes_graph_aware():
    then = then_from(CORRECT, match_named_graphs=True)
    actual = load_dataset_from_file(CORRECT, GivenSpec()).value

    assert isinstance(check_result(update_spec(then), actual), SpecPassed)


def test_the_failure_carries_the_triples_that_moved():
    then = then_from(SHUFFLED, match_named_graphs=True)
    actual = load_dataset_from_file(CORRECT, GivenSpec()).value

    result = check_result(update_spec(then), actual)
    comparison = result.graph_comparison

    # Every triple exists on both sides, so a flat diff would be empty. Reported
    # per graph, each side is missing what the other has in that graph.
    assert len(comparison.in_expected_not_in_actual) > 0
    assert len(comparison.in_actual_not_in_expected) > 0


def test_the_differing_graphs_are_named_in_the_log():
    """Which layer moved, not just that something did.

    A handler on mustrd's own logger rather than caplog: logger_setup sets
    propagate = False on the mustrd package, so once anything in a run has
    initialised logging, caplog (which listens at root) sees nothing and this test
    would pass or fail depending on ordering.
    """
    import logging

    records = []

    class Collect(logging.Handler):
        def emit(self, record):
            records.append(record.getMessage())

    logger = logging.getLogger("mustrd.mustrd")
    handler = Collect(level=logging.ERROR)
    logger.addHandler(handler)
    previous = logger.level
    logger.setLevel(logging.ERROR)
    try:
        then = then_from(SHUFFLED, match_named_graphs=True)
        actual = load_dataset_from_file(CORRECT, GivenSpec()).value
        check_result(update_spec(then), actual)
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous)

    named = [m for m in records if "named graph(s) differ" in m]
    assert named, f"the failure should say which graphs differ; got {records}"
    assert "graph-a" in named[0] and "graph-b" in named[0]


# --------------------------------------------------------------------------
# graphs_by_name, which has to cope with results that carry no contexts
# --------------------------------------------------------------------------
def test_a_flat_result_reads_as_one_default_graph():
    flat = Graph().parse(
        data="<https://a.example/s> <https://a.example/p> <https://a.example/o> .",
        format="turtle")

    names = graphs_by_name(flat)

    assert len(names) == 1
    assert len(next(iter(names.values()))) == 1


def test_an_empty_default_graph_is_not_counted_as_a_graph():
    # A quad file puts nothing in the default graph, and rdflib still offers one.
    # Counting it would make every graph-aware comparison see a phantom.
    dataset = load_dataset_from_file(CORRECT, GivenSpec()).value

    assert set(graphs_by_name(dataset)) == {
        str(TEST_DATA["graph-a"]), str(TEST_DATA["graph-b"])}


@pytest.mark.parametrize("path", [CORRECT, SHUFFLED])
def test_both_fixtures_hold_the_same_triples(path):
    # If this ever stops being true the pair no longer isolates graph placement.
    from mustrd.spec_component import flatten_to_graph
    from rdflib.compare import isomorphic

    one = flatten_to_graph(load_dataset_from_file(CORRECT, GivenSpec()).value)
    other = flatten_to_graph(load_dataset_from_file(path, GivenSpec()).value)

    assert isomorphic(one, other)
