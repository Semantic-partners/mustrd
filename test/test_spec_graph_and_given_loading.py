"""Two parsing bugs that surfaced as messages about the wrong thing.

A `.trig` given was parsed into a plain Graph, which cannot see the quads the
parser puts in the store's named contexts — so the given came back EMPTY, and an
empty given read as no given at all: "Unable to run Inherited State tests on
Rdflib", about a feature the spec never mentioned.

A file was re-parsed once per spec it declared and every parse merged into the
shared spec graph, so each spec ended up with N `then` nodes and a table `then`
was rejected as unimplemented — naming one spec while every spec in the file
failed.

"""

from pathlib import Path

import pytest
from rdflib import ConjunctiveGraph, Graph, Namespace

from mustrd.mustrd import (
    Specification,
    SpecInvalid,
    add_spec_validation,
    run_spec,
)
from mustrd.namespace import MUST, TRIPLESTORE
from mustrd.spec_component import (
    GivenSpec,
    TableThenSpec,
    ThenSpec,
    load_dataset_from_file,
    parse_spec_component,
)

TEST_DATA = Namespace("https://semanticpartners.com/data/test/")
TRIPLE_STORE = {"type": TRIPLESTORE.RdfLib}

TRIG = """
@prefix test-data: <https://semanticpartners.com/data/test/> .
test-data:graph-a { test-data:sub test-data:pred test-data:obj . }
test-data:graph-b { test-data:sub2 test-data:pred2 test-data:obj2 . }
"""

TWO_SPECS = """
@prefix must:      <https://mustrd.org/model/> .
@prefix test-data: <https://semanticpartners.com/data/test/> .

test-data:first a must:TestSpec ;
    must:when [ a must:TextSparqlSource ;
                must:queryText "SELECT ?s WHERE { ?s ?p ?o }" ;
                must:queryType must:SelectSparql ] ;
    must:then [ a must:TableDataset ;
                must:hasRow [ must:hasBinding [ must:variable "s" ;
                                                must:boundValue test-data:sub ] ] ] .

test-data:second a must:TestSpec ;
    must:when [ a must:TextSparqlSource ;
                must:queryText "SELECT ?o WHERE { ?s ?p ?o }" ;
                must:queryType must:SelectSparql ] ;
    must:then [ a must:TableDataset ;
                must:hasRow [ must:hasBinding [ must:variable "o" ;
                                                must:boundValue test-data:obj ] ] ] .
"""


@pytest.fixture
def trig_file(tmp_path: Path) -> Path:
    path = tmp_path / "given.trig"
    path.write_text(TRIG)
    return path


def test_a_trig_given_keeps_its_named_graphs(trig_file):
    given = load_dataset_from_file(trig_file, GivenSpec()).value

    assert isinstance(given, ConjunctiveGraph)
    contexts = {str(context.identifier) for context in given.contexts()}
    assert str(TEST_DATA["graph-a"]) in contexts
    assert str(TEST_DATA["graph-b"]) in contexts


def test_a_trig_given_resolves_a_graph_clause(trig_file):
    given = load_dataset_from_file(trig_file, GivenSpec()).value

    rows = list(given.query(
        "PREFIX test-data: <https://semanticpartners.com/data/test/> "
        "SELECT ?s WHERE { GRAPH test-data:graph-a { ?s ?p ?o } }"))

    assert [str(row.s) for row in rows] == [str(TEST_DATA.sub)]


def test_a_trig_given_still_reads_as_the_union(trig_file):
    given = load_dataset_from_file(trig_file, GivenSpec()).value

    rows = given.query("SELECT ?s WHERE { ?s ?p ?o }")

    assert {str(row.s) for row in rows} == {str(TEST_DATA.sub), str(TEST_DATA.sub2)}


def test_a_trig_given_iterates_as_triples(trig_file):
    # Coverage, reporting and graph comparison all iterate a given expecting
    # triples. A Dataset would hand them quads.
    given = load_dataset_from_file(trig_file, GivenSpec()).value

    assert all(len(statement) == 3 for statement in given)


def test_a_trig_then_is_flattened(trig_file):
    # A `then` is compared against the query's result graph, which has no named
    # graphs to compare against — so it keeps every triple but no contexts.
    then = load_dataset_from_file(trig_file, ThenSpec()).value

    assert isinstance(then, Graph)
    assert not isinstance(then, ConjunctiveGraph)
    assert len(then) == 2


def test_an_empty_given_is_not_reported_as_inherited_state():
    spec = Specification(
        TEST_DATA.empty_given_spec,
        TRIPLE_STORE,
        Graph(),  # parsed to nothing — NOT the same as having no given
        [],
        ThenSpec(),
    )

    result = run_spec(spec)

    assert not (
        isinstance(result, SpecInvalid)
        and "Inherited State" in str(result.message)
    )


def test_no_given_at_all_is_still_inherited_state():
    spec = Specification(
        TEST_DATA.inherited_state_spec, TRIPLE_STORE, None, [], ThenSpec()
    )

    result = run_spec(spec)

    assert isinstance(result, SpecInvalid)
    assert "Unable to run Inherited State tests on Rdflib" in result.message


def test_a_file_of_two_specs_is_merged_once(tmp_path: Path):
    path = tmp_path / "two_specs.mustrd.ttl"
    path.write_text(TWO_SPECS)
    file_graph = Graph().parse(path)
    spec_graph = Graph()

    add_spec_validation(
        file_graph, set(), path, [TRIPLE_STORE], [], [], spec_graph
    )

    for spec_uri in (TEST_DATA.first, TEST_DATA.second):
        then_nodes = list(spec_graph.objects(spec_uri, MUST.then))
        assert len(then_nodes) == 1, (
            f"{spec_uri} has {len(then_nodes)} then nodes; the file was merged "
            "once per spec")


def test_each_of_two_table_specs_in_a_file_parses(tmp_path: Path):
    path = tmp_path / "two_specs.mustrd.ttl"
    path.write_text(TWO_SPECS)
    file_graph = Graph().parse(path)
    spec_graph = Graph()
    add_spec_validation(
        file_graph, set(), path, [TRIPLE_STORE], [], [], spec_graph
    )

    for spec_uri in (TEST_DATA.first, TEST_DATA.second):
        then = parse_spec_component(
            subject=spec_uri,
            predicate=MUST.then,
            spec_graph=spec_graph,
            run_config={},
            mustrd_triple_store=TRIPLE_STORE,
        )
        assert isinstance(then, TableThenSpec)
        assert then.value.shape[0] == 1


def test_a_file_of_two_specs_records_both_uris(tmp_path: Path):
    path = tmp_path / "two_specs.mustrd.ttl"
    path.write_text(TWO_SPECS)
    subject_uris = set()

    add_spec_validation(
        Graph().parse(path), subject_uris, path, [TRIPLE_STORE], [], [], Graph()
    )

    assert subject_uris == {TEST_DATA.first, TEST_DATA.second}


def test_a_file_with_errors_contributes_nothing(tmp_path: Path):
    path = tmp_path / "two_specs.mustrd.ttl"
    path.write_text(TWO_SPECS)
    spec_graph = Graph()
    invalid_specs = []

    add_spec_validation(
        Graph().parse(path), set(), path, [TRIPLE_STORE],
        ["a shape did not conform"], invalid_specs, spec_graph,
    )

    assert len(spec_graph) == 0
    assert len(invalid_specs) == 2
    assert all(isinstance(spec, SpecInvalid) for spec in invalid_specs)


def test_a_duplicate_spec_uri_is_still_rejected(tmp_path: Path):
    path = tmp_path / "two_specs.mustrd.ttl"
    path.write_text(TWO_SPECS)
    already_seen = {TEST_DATA.first}
    invalid_specs = []

    add_spec_validation(
        Graph().parse(path), already_seen, path, [TRIPLE_STORE], [],
        invalid_specs, Graph(),
    )

    assert TEST_DATA["first_DUPLICATE"] in {spec.spec_uri for spec in invalid_specs}
