"""Numbers compared within a tolerance: on the triple store config, the spec,
the then, or one column of the then. The narrowest level that declares one wins."""
import pytest
from rdflib import Graph

from mustrd.mustrd import (SpecPassed, SelectSpecFailure, Specification, check_result, run_when,
                           get_triple_stores, table_diff_to_markdown)
from mustrd.namespace import MUST, TRIPLESTORE
from mustrd.spec_component import Tolerance, parse_spec_component, read_tolerance
from test.addspec_source_file_to_spec_graph import parse_spec
from test.test_general import validate_then
from test.test_select_spec import TEST_DATA

X = "http://www.w3.org/2001/XMLSchema#"
T = "https://semanticpartners.com/data/test/"

# What 0.1 + 0.2 comes to in a double, against a then that says 0.3.
GIVEN = f'''@prefix t: <{T}> .
    @prefix xsd: <{X}> .
    t:a t:pred "0.30000000000000004"^^xsd:double ; t:label "1" .'''

INLINE_THEN = """[ a must:TableDataset ; {extra}
    must:hasRow [ must:hasBinding [ must:variable "s" ; must:boundValue test-data:a ] ,
                                  [ must:variable "o" ; must:boundValue "0.3"^^xsd:double ] ] ]"""


def run(then_ttl: str, spec_extra: str = "", store_tolerance: Tolerance = None, predicate: str = "pred"):
    given = Graph().parse(data=GIVEN, format="ttl")
    spec = f"""
        @prefix must: <https://mustrd.org/model/> .
        @prefix xsd: <{X}> .
        @prefix test-data: <{T}> .
        test-data:my_first_spec a must:TestSpec ; {spec_extra}
            must:when [ a must:TextSparqlSource ;
                must:queryText "select ?s ?o {{ ?s <{T}{predicate}> ?o }}" ;
                must:queryType must:SelectSparql ] ;
            must:then {then_ttl} .
        """
    triple_store = {"type": TRIPLESTORE.RdfLib, "given": given}
    if store_tolerance:
        triple_store["tolerance"] = store_tolerance
    spec_uri = TEST_DATA.my_first_spec
    spec_graph = parse_spec(spec, spec_uri, __name__)
    run_config = {'spec_path': ""}
    when = parse_spec_component(subject=spec_uri, predicate=MUST.when, spec_graph=spec_graph,
                                run_config=run_config, mustrd_triple_store=triple_store)
    then = parse_spec_component(subject=spec_uri, predicate=MUST.then, spec_graph=spec_graph,
                                run_config=run_config, mustrd_triple_store=triple_store)
    spec = Specification(spec_uri, triple_store, given, when, then,
                         tolerance=read_tolerance(spec_graph, spec_uri))
    return check_result(spec, run_when(spec_uri, triple_store, when[0]))


def test_exact_by_default():
    assert isinstance(run(INLINE_THEN.format(extra="")), SelectSpecFailure)


@pytest.mark.parametrize("then_extra, spec_extra, store", [
    ("must:tolerance 1e-9 ;", "", None),
    ("must:relativeTolerance 1e-9 ;", "", None),
    ("", "must:tolerance 0.000001 ;", None),
    ("", "", Tolerance(absolute=1e-9)),
    ('must:columnTolerance [ must:variable "o" ; must:tolerance 1e-9 ] ;', "", None),
])
def test_each_level_passes_a_near_miss(then_extra, spec_extra, store):
    result = run(INLINE_THEN.format(extra=then_extra), spec_extra, store)
    assert isinstance(result, SpecPassed), getattr(result, "message", result)


def test_narrowest_level_wins():
    # The spec is generous; the column is not, and replaces it.
    result = run(INLINE_THEN.format(
        extra='must:columnTolerance [ must:variable "o" ; must:tolerance 1e-20 ] ;'),
        "must:tolerance 1 ;")
    assert isinstance(result, SelectSpecFailure)


def test_out_of_tolerance_fails_and_shows_the_real_values():
    then = INLINE_THEN.replace('"0.3"', '"0.31"').format(extra="must:tolerance 0.001 ;")
    result = run(then)
    assert isinstance(result, SelectSpecFailure)
    diff = table_diff_to_markdown(result.table_comparison)
    assert "0.31" in diff and "0.30000000000000004" in diff


def test_datatype_still_has_to_match():
    then = INLINE_THEN.replace('"0.3"^^xsd:double', '"0.3"^^xsd:decimal').format(
        extra="must:tolerance 1 ;")
    assert isinstance(run(then), SelectSpecFailure)


def test_wider_levels_skip_columns_that_are_not_doubles():
    # ?o is a string here, so a tolerance of 1 on the spec does not make "1" match "2".
    then = INLINE_THEN.replace('"0.3"^^xsd:double', '"2"').format(extra="")
    assert isinstance(run(then, "must:tolerance 1 ;", predicate="label"), SelectSpecFailure)


@pytest.mark.parametrize("then_extra", [
    'must:columnTolerance [ must:variable "o" ; must:tolerance 1e-9 ] ;',
    # No datatype columns in the CSV: the store's own xsd:double says ?o is a number.
    "must:tolerance 1e-9 ;",
])
def test_csv_without_datatype_columns(tmp_path, then_extra):
    csv = tmp_path / "then.csv"
    csv.write_text(f"s,o\n{T}a,0.3\n")
    then = f'[ a must:FileDataset ; {then_extra} must:file "{csv.as_posix()}" ]'
    result = run(then)
    assert isinstance(result, SpecPassed), getattr(result, "message", result)


def test_csv_without_tolerance_still_exact(tmp_path):
    csv = tmp_path / "then.csv"
    csv.write_text(f"s,o\n{T}a,0.3\n")
    assert isinstance(run(f'[ a must:FileDataset ; must:file "{csv.as_posix()}" ]'), SelectSpecFailure)


def test_triple_store_config_carries_tolerance():
    config = Graph().parse(data="""
        @prefix triplestore: <https://mustrd.org/triplestore/> .
        @prefix must: <https://mustrd.org/model/> .
        <urn:store> a triplestore:RdfLib ; must:tolerance 0.01 ; must:relativeTolerance 1e-6 .
        """, format="ttl")
    store, = get_triple_stores(config)
    assert store["tolerance"] == Tolerance(absolute=0.01, relative=1e-6)


def test_triple_store_config_without_tolerance_is_unchanged():
    config = Graph().parse(data="""
        @prefix triplestore: <https://mustrd.org/triplestore/> .
        <urn:store> a triplestore:RdfLib .
        """, format="ttl")
    store, = get_triple_stores(config)
    assert "tolerance" not in store


@pytest.mark.parametrize("then_ttl", [
    '[ a must:FileDataset ; must:file "e.csv" ; must:tolerance -1 ]',
    '[ a must:FileDataset ; must:file "e.csv" ; must:tolerance "small" ]',
    '[ a must:FileDataset ; must:file "e.csv" ; must:relativeTolerance 1, 2 ]',
    '[ a must:FileDataset ; must:file "e.csv" ; must:columnTolerance [ must:tolerance 1 ] ]',
])
def test_shapes_reject(then_ttl):
    conforms, _, text = validate_then(then_ttl)
    assert conforms is False, text


@pytest.mark.parametrize("then_ttl", [
    '[ a must:FileDataset ; must:file "e.csv" ; must:tolerance 0.01 ; must:relativeTolerance 1e-9 ]',
    '[ a must:FileDataset ; must:file "e.csv" ; must:columnTolerance [ must:variable "o" ; must:tolerance 1 ] ]',
])
def test_shapes_accept(then_ttl):
    conforms, _, text = validate_then(then_ttl)
    assert conforms is True, text
