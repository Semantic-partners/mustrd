"""mustrd must not print deprecation warnings at its users.

A warning a user cannot act on is noise that trains them to ignore warnings they
*can* act on. This appeared in the wild as fourteen copies per run of

    spec_component.py:390: DeprecationWarning: ConjunctiveGraph is deprecated,
    use Dataset instead.

pointing at a mustrd line, in a project that had no way to change it.

Two kinds are covered here. Ours — reaching an rdflib API that rdflib has
deprecated — is a bug and this fails on it. rdflib reaching its *own* deprecated
internals (its TriG parser builds a ConjunctiveGraph; `Dataset.serialize` uses
`default_context`) is not ours to fix, and is silenced at the call site rather
than passed on.
"""

import warnings
from pathlib import Path

import pytest
from rdflib import Graph, Namespace

from mustrd.mustrd import Specification, run_spec, serialise_quietly
from mustrd.namespace import TRIPLESTORE
from mustrd.reporting import coverage_spec
from mustrd.spec_component import (
    GivenSpec, ThenSpec, UpdatableDataset, flatten_to_graph, load_dataset_from_file,
)

TEST_DATA = Namespace("https://semanticpartners.com/data/test/")
TRIPLE_STORE = {"type": TRIPLESTORE.RdfLib}

TRIG = """
@prefix test-data: <https://semanticpartners.com/data/test/> .
test-data:graph-a { test-data:sub test-data:pred test-data:obj . }
test-data:graph-b { test-data:sub2 test-data:pred2 test-data:obj2 . }
"""

TTL = "<https://a.example/s> <https://a.example/p> <https://a.example/o> .\n"


def deprecations_from_mustrd(work):
    """Run `work`, returning any DeprecationWarning attributed to mustrd's code."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        work()
    return [
        f"{Path(w.filename).name}:{w.lineno} {w.message}"
        for w in caught
        if issubclass(w.category, DeprecationWarning)
        and f"{Path(w.filename).parent.name}" == "mustrd"
    ]


@pytest.fixture
def trig_file(tmp_path: Path) -> Path:
    path = tmp_path / "given.trig"
    path.write_text(TRIG)
    return path


@pytest.fixture
def ttl_file(tmp_path: Path) -> Path:
    path = tmp_path / "given.ttl"
    path.write_text(TTL)
    return path


def test_loading_a_quad_given_is_quiet(trig_file):
    # The one from the wild: 14 per run, naming a mustrd line.
    assert deprecations_from_mustrd(
        lambda: load_dataset_from_file(trig_file, GivenSpec())) == []


def test_loading_a_triples_given_is_quiet(ttl_file):
    assert deprecations_from_mustrd(
        lambda: load_dataset_from_file(ttl_file, GivenSpec())) == []


def test_loading_a_then_is_quiet(trig_file):
    assert deprecations_from_mustrd(
        lambda: load_dataset_from_file(trig_file, ThenSpec())) == []


def test_levelling_a_given_is_quiet(trig_file):
    given = load_dataset_from_file(trig_file, GivenSpec()).value
    assert deprecations_from_mustrd(lambda: flatten_to_graph(given)) == []


def test_serialising_a_given_is_quiet(trig_file):
    given = load_dataset_from_file(trig_file, GivenSpec()).value
    assert deprecations_from_mustrd(lambda: serialise_quietly(given)) == []


def test_serialising_keeps_the_named_graphs(trig_file):
    # Quietness must not have cost the graphs: trig, not turtle, for quads.
    given = load_dataset_from_file(trig_file, GivenSpec()).value

    text = serialise_quietly(given)

    assert "graph-a" in text and "graph-b" in text


def test_projecting_a_spec_for_reporting_is_quiet(trig_file):
    given = load_dataset_from_file(trig_file, GivenSpec()).value
    spec = Specification(
        TEST_DATA.a_spec, TRIPLE_STORE, given, [], ThenSpec())

    assert deprecations_from_mustrd(
        lambda: coverage_spec(spec, "passed", "a_spec")) == []


def test_running_a_spec_is_quiet(trig_file):
    given = load_dataset_from_file(trig_file, GivenSpec()).value
    then = ThenSpec()
    then.value = Graph()
    spec = Specification(TEST_DATA.a_spec, TRIPLE_STORE, given, [], then)

    assert deprecations_from_mustrd(lambda: run_spec(spec)) == []


def test_running_a_spec_is_quiet_with_debug_logging_on(trig_file, caplog):
    # The debug path formats and serialises the given, which is where the
    # deprecated rdflib internals get reached.
    import logging
    given = load_dataset_from_file(trig_file, GivenSpec()).value
    then = ThenSpec()
    then.value = Graph()
    spec = Specification(TEST_DATA.a_spec, TRIPLE_STORE, given, [], then)

    with caplog.at_level(logging.DEBUG, logger="mustrd.mustrd"):
        assert deprecations_from_mustrd(lambda: run_spec(spec)) == []


# ---------------------------------------------------------------------------
# The upstream bug that stopped mustrd moving off ConjunctiveGraph sooner, and
# the tripwire for when it is fixed.
# ---------------------------------------------------------------------------
INSERT_DATA = "INSERT DATA { <https://a.example/s> <https://a.example/p> <https://a.example/o> }"


def test_insert_data_is_broken_on_a_plain_dataset():
    """rdflib 7.6: `evalInsertData` does `g += u.triples` with the dataset as `g`,
    and `Dataset.__iadd__` unpacks quads.

    TRIPWIRE. When this test fails, rdflib has fixed it — at which point
    `UpdatableDataset` can become a plain `Dataset` and be deleted.
    """
    from rdflib import Dataset

    with pytest.raises(ValueError, match="expected 4, got 3"):
        Dataset(default_union=True).update(INSERT_DATA)


def test_insert_data_works_on_our_dataset():
    dataset = UpdatableDataset(default_union=True)

    dataset.update(INSERT_DATA)

    assert len(dataset) == 1


def test_insert_data_into_a_named_graph_still_lands_there():
    # The repair must not have flattened rdflib's own quad handling.
    dataset = UpdatableDataset(default_union=True)

    dataset.update(
        "INSERT DATA { GRAPH <https://a.example/g> "
        "{ <https://a.example/s> <https://a.example/p> <https://a.example/o> } }")

    assert "https://a.example/g" in {str(g.identifier) for g in dataset.graphs()}


def test_delete_data_and_insert_where_still_work():
    dataset = UpdatableDataset(default_union=True)
    dataset.update(INSERT_DATA)

    dataset.update("INSERT { ?s <https://a.example/p2> ?o } "
                   "WHERE { ?s <https://a.example/p> ?o }")
    assert len(dataset) == 2

    dataset.update(INSERT_DATA.replace("INSERT", "DELETE"))
    assert len(dataset) == 1


def test_the_suppression_does_not_hide_mustrd_s_own_deprecations():
    """The filter is scoped to rdflib, not to DeprecationWarning generally.

    If it muted everything, this whole file would pass vacuously and the next
    deprecated call mustrd makes would ship silently.
    """
    from mustrd.utils import rdflib_internals_quiet

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with rdflib_internals_quiet():
            warnings.warn("mustrd did something deprecated", DeprecationWarning)

    assert [str(w.message) for w in caught] == ["mustrd did something deprecated"]


def test_the_suppression_still_reports_mustrd_calling_a_deprecated_rdflib_api():
    """The scoping is by CALLER, which is what makes it safe.

    rdflib raises these with `stacklevel=2`, so the warning is attributed to
    whoever called in. A `module="rdflib.*"` filter therefore silences
    rdflib-calling-its-own-deprecated-internals and nothing else: if mustrd
    reaches for a deprecated API directly, it is still reported even inside the
    suppression.
    """
    from rdflib import Dataset

    from mustrd.utils import rdflib_internals_quiet

    dataset = Dataset(default_union=True)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with rdflib_internals_quiet():
            dataset.default_context  # this module is the caller, so: reported

    assert [str(w.message) for w in caught
            if issubclass(w.category, DeprecationWarning)] == [
        "Dataset.default_context is deprecated, use Dataset.default_graph instead."]
