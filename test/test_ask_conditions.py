"""must:AskConditions: conditions on a SELECT's result, checked by ASK queries in
the store, so no row of the result reaches mustrd or its reports."""
import subprocess
import sys

import pytest
from rdflib import Dataset, URIRef

from mustrd.ask_rewrite import (
    Condition, ask_for_condition, ask_for_row_count, inline_bindings,
    split_select, subquery_rewriter,
)
from mustrd.cli import main
from mustrd.utils import rdflib_internals_quiet

DATA = """@prefix ex: <https://example.org/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
ex:p1 ex:name "Alice Secret" ; ex:dob "1980-01-01"^^xsd:date .
ex:p2 ex:name "Bob Secret" .
<https://example.org/g> { ex:p3 ex:name "Carol Secret" . }
"""

PEOPLE = """PREFIX ex: <https://example.org/>
SELECT ?p ?name ?dob WHERE { ?p ex:name ?name OPTIONAL { ?p ex:dob ?dob } }"""


@pytest.fixture
def dataset():
    d = Dataset(default_union=True)
    with rdflib_internals_quiet():
        d.parse(data=DATA, format="trig")
    return d


def ask(dataset, query):
    with rdflib_internals_quiet():
        return bool(dataset.query(query).askAnswer)


# --- splitting the SELECT -------------------------------------------------------

def test_prologue_and_body_are_separated():
    parts = split_select(PEOPLE)
    assert parts.prologue == "PREFIX ex: <https://example.org/>\n"
    assert parts.query.startswith("SELECT ?p")
    assert parts.dataset == ""


def test_from_clauses_move_to_the_outer_query():
    parts = split_select("PREFIX ex: <https://example.org/>\n"
                         "SELECT ?p FROM <https://example.org/a> FROM NAMED ex:b\n"
                         "WHERE { ?p ?q ?o }")
    assert parts.dataset == "FROM <https://example.org/a> FROM NAMED ex:b"
    assert "FROM" not in parts.query


def test_keywords_in_strings_comments_iris_and_names_are_ignored():
    query = ('PREFIX select: <https://example.org/from/>\n'
             '# SELECT FROM in a comment\n'
             'SELECT ?from (CONCAT("{ FROM", ?x) AS ?y) ?z\n'
             'WHERE { ?from select:from ?x . ?x <https://e.org/FROM> ?z }')
    parts = split_select(query)
    assert parts.prologue.endswith("# SELECT FROM in a comment\n")
    assert parts.dataset == ""
    assert parts.query == query[len(parts.prologue):]


def test_a_query_that_is_not_a_select_is_refused():
    with pytest.raises(ValueError, match="Only a SELECT"):
        split_select("CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o }")


# --- what the ASKs mean ---------------------------------------------------------

@pytest.mark.parametrize("min_rows, max_rows, expected", [
    (1, None, True), (3, 3, True), (4, None, False), (1, 2, False), (0, None, True)])
def test_row_count(dataset, min_rows, max_rows, expected):
    assert ask(dataset, ask_for_row_count(PEOPLE, min_rows, max_rows)) is expected


def test_every_row_fails_on_a_row_where_the_variable_is_unbound(dataset):
    # Two people have no date of birth. FILTER alone would drop those rows and
    # pass; they must count as failures.
    assert not ask(dataset, ask_for_condition(PEOPLE, Condition("?dob < NOW()")))


def test_every_row_and_some_row(dataset):
    assert ask(dataset, ask_for_condition(PEOPLE, Condition("isIRI(?p)")))
    assert ask(dataset, ask_for_condition(PEOPLE, Condition("?dob < NOW()", every_row=False)))
    assert not ask(dataset, ask_for_condition(PEOPLE, Condition("?dob > NOW()", every_row=False)))


def test_from_still_narrows_the_dataset(dataset):
    query = ("PREFIX ex: <https://example.org/>\n"
             "SELECT ?p FROM ex:g WHERE { ?p ex:name ?n }")
    assert ask(dataset, ask_for_row_count(query, 1, 1))


def test_aggregates_ordering_and_limits_keep_their_meaning(dataset):
    counted = "PREFIX ex: <https://example.org/> SELECT (COUNT(?p) AS ?n) WHERE { ?p ex:name ?x }"
    assert ask(dataset, ask_for_condition(counted, Condition("?n = 3")))
    limited = PEOPLE + " ORDER BY ?p LIMIT 2"
    assert ask(dataset, ask_for_row_count(limited, 2, 2))


def test_a_binding_reaches_a_variable_the_select_does_not_project(dataset):
    # Inlined into the SELECT itself: at the outer ASK it would bind nothing.
    query = ("PREFIX ex: <https://example.org/>\n"
             "SELECT ?name WHERE{ ?p ex:name ?name }")
    bound = inline_bindings(query, {"p": URIRef("https://example.org/p2")})
    assert "WHERE{\nVALUES ?p { <https://example.org/p2> }" in bound
    assert ask(dataset, ask_for_row_count(bound, 1, 1))


def test_the_default_rewriter_describes_each_check_without_data():
    checks = subquery_rewriter(PEOPLE, [Condition("isIRI(?p)")], 1, None)
    assert [c.description for c in checks] == ["at least 1 row", "every row: isIRI(?p)"]


# --- end to end -----------------------------------------------------------------

CONFIG = """@prefix : <https://mustrd.org/mustrdTest/> .
@prefix triplestore: <https://mustrd.org/triplestore/> .
:ask a :MustrdTest ; :hasSpecPath "specs" ; :hasDataPath "data" ;
    :hasPytestPath "ask" ; :filterOnTripleStore triplestore:RdfLib .
"""

SPEC = """@prefix must: <https://mustrd.org/model/> .
@prefix ex:   <https://example.org/> .
ex:{name} a must:TestSpec ;
    must:given [ a must:FileDataset ; must:file "people.trig" ] ;
    must:when  [ a must:FileSparqlSource ; must:file "people.rq" ;
                 must:queryType must:{query_type} ] ;
    must:then  [ a must:AskConditions ;
{then}
               ] .
"""


def write_spec(spec_dir, name, then, query_type="SelectSparql"):
    (spec_dir / "specs" / f"{name}.mustrd.ttl").write_text(
        SPEC.format(name=name, then=then, query_type=query_type))


@pytest.fixture
def spec_dir(tmp_path):
    (tmp_path / "specs").mkdir()
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "people.trig").write_text(DATA)
    (tmp_path / "data" / "people.rq").write_text(PEOPLE)
    (tmp_path / "config.ttl").write_text(CONFIG)
    write_spec(tmp_path, "rows", "must:minRows 3 ; must:maxRows 3 ;")
    return tmp_path


def report(spec_dir, capsys):
    # -v, so every failure is printed in full.
    code = main(["run", "--config", str(spec_dir / "config.ttl"), "-v"])
    captured = capsys.readouterr()
    return code, captured.out + captured.err


def test_a_spec_whose_conditions_hold_passes(spec_dir, capsys):
    write_spec(spec_dir, "iris", """
        must:condition [ must:filter "isIRI(?p)" ] ,
                       [ must:filter "BOUND(?dob)" ; must:holdsFor must:SomeRow ] ;""")
    code, out = report(spec_dir, capsys)
    assert code == 0, out


def test_a_failure_names_the_checks_and_shows_no_data(spec_dir, capsys):
    write_spec(spec_dir, "dob", """
        must:minRows 5 ;
        must:condition [ must:filter "?dob < NOW()" ] ,
                       [ must:filter "isIRI(?p)" ] ;""")
    code, out = report(spec_dir, capsys)
    assert code == 1
    assert "Expected at least 5 rows; every row: ?dob < NOW() (2 of 3 checks failed)" in out


def test_a_failure_under_pytest_shows_no_result_data(spec_dir):
    # As CI runs it. (`-v` on the CLI logs the given at DEBUG, which is a
    # different matter: a remote spec inherits its data and has no given.)
    write_spec(spec_dir, "dob", """
        must:minRows 5 ;
        must:condition [ must:filter "?dob < NOW()" ] ;""")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "--mustrd",
         "--config", "config.ttl", "-rA"],
        cwd=spec_dir, capture_output=True, text=True)
    out = result.stdout + result.stderr
    assert result.returncode == 1, out
    assert "Expected at least 5 rows; every row: ?dob < NOW()" in out
    assert "Secret" not in out


def test_conditions_on_a_construct_are_invalid(spec_dir, capsys):
    (spec_dir / "specs" / "rows.mustrd.ttl").unlink()
    write_spec(spec_dir, "construct", "must:minRows 1 ;", query_type="ConstructSparql")
    code, out = report(spec_dir, capsys)
    assert code == 1
    assert "must:AskConditions applies to a SELECT only" in out
