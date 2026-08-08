"""The one-line summary above a table diff.

On a value- or datatype-only mismatch the expected and actual shapes are
identical, so "Expected 1 row(s) and 1 column(s), got 1 row(s) and 1 column(s)"
reads as though nothing is wrong — and on a wide result the column that actually
differs can sit off the right-hand edge of the diff below it. The summary names
the differing columns in exactly that case, and stays out of the way when the
shapes already carry the news.

https://github.com/Semantic-partners/mustrd/issues/240
"""

import pandas
import pytest

from mustrd.mustrd import build_summary_message, describe_differing_columns

XSD = "http://www.w3.org/2001/XMLSchema#"


def diff_of(expected: dict, actual: dict) -> pandas.DataFrame:
    """The (column, expected|actual) MultiIndex frame mustrd compares with."""
    return pandas.DataFrame(expected).compare(
        pandas.DataFrame(actual), result_names=("expected", "actual")
    )


def test_shapes_match_so_the_differing_column_is_named():
    # A datatype-only mismatch IS the two type IRIs, so the summary carries them
    # and the reader never has to reach the diff.
    df_diff = diff_of(
        {"month": ["2025-01"], "month_datatype": [XSD + "string"]},
        {"month": ["2025-01"], "month_datatype": [XSD + "gYearMonth"]},
    )
    message = build_summary_message(1, 1, 1, 1, df_diff)

    assert message == (
        "Expected 1 row(s) and 1 column(s), got 1 row(s) and 1 column(s)"
        " — differs in: month (datatype: expected xsd:string, actual xsd:gYearMonth)"
    )


def test_rows_agreeing_on_one_pair_of_types_name_it():
    df_diff = diff_of(
        {"m": ["a", "b"], "m_datatype": [XSD + "string"] * 2},
        {"m": ["a", "b"], "m_datatype": [XSD + "gYearMonth"] * 2},
    )

    assert describe_differing_columns(df_diff) == (
        "m (datatype: expected xsd:string, actual xsd:gYearMonth)"
    )


def test_rows_disagreeing_on_types_fall_back_to_a_bare_datatype():
    # Naming a pair only some rows have would be worse than naming none; the
    # diff below still has every row.
    df_diff = diff_of(
        {"m": ["a", "b"], "m_datatype": [XSD + "string"] * 2},
        {"m": ["a", "b"], "m_datatype": [XSD + "gYearMonth", XSD + "date"]},
    )

    assert describe_differing_columns(df_diff) == "m (datatype)"


def test_a_datatype_outside_the_known_prefixes_stays_a_full_iri():
    df_diff = diff_of(
        {"m": ["a"], "m_datatype": ["http://example.org/my#T"]},
        {"m": ["a"], "m_datatype": [XSD + "string"]},
    )

    assert describe_differing_columns(df_diff) == (
        "m (datatype: expected <http://example.org/my#T>, actual xsd:string)"
    )


def test_a_value_column_and_a_datatype_only_column_together():
    df_diff = diff_of(
        {"s": ["x"], "s_datatype": [XSD + "string"],
         "m": ["a"], "m_datatype": [XSD + "string"]},
        {"s": ["y"], "s_datatype": [XSD + "string"],
         "m": ["a"], "m_datatype": [XSD + "date"]},
    )

    assert describe_differing_columns(df_diff) == (
        's (expected "x", actual "y"), '
        "m (datatype: expected xsd:string, actual xsd:date)"
    )


def test_shapes_differ_so_the_column_list_is_left_off():
    # The row counts already say what is wrong; listing every column here would
    # be noise, and on a wide result a long one.
    df_diff = diff_of(
        {"s": ["a", "b"], "s_datatype": ["u", "u"]},
        {"s": ["c", "d"], "s_datatype": ["u", "u"]},
    )
    message = build_summary_message(1, 3, 2, 3, df_diff)

    assert message == "Expected 1 row(s) and 3 column(s), got 2 row(s) and 3 column(s)"


def test_no_diff_adds_nothing():
    assert build_summary_message(1, 1, 1, 1, pandas.DataFrame()) == (
        "Expected 1 row(s) and 1 column(s), got 1 row(s) and 1 column(s)"
    )
    assert build_summary_message(0, 0, 0, 0) == (
        "Expected 0 row(s) and 0 column(s), got 0 row(s) and 0 column(s)"
    )


def test_a_binding_whose_value_differs_is_named_once():
    # A changed value almost always changes the datatype column too. Saying
    # "o (...), o (datatype: ...)" adds nothing, so (datatype) is reserved for
    # the case the reader cannot otherwise see: same text, different type.
    df_diff = diff_of(
        {"o": ["1"], "o_datatype": [XSD + "integer"]},
        {"o": ["2"], "o_datatype": [XSD + "string"]},
    )

    assert describe_differing_columns(df_diff) == 'o (expected "1", actual "2")'


def test_columns_keep_the_order_of_the_diff():
    df_diff = diff_of(
        {"s": ["a"], "p": ["b"], "o": ["c"]},
        {"s": ["x"], "p": ["y"], "o": ["z"]},
    )

    assert describe_differing_columns(df_diff) == (
        's (expected "a", actual "x"), p (expected "b", actual "y"), '
        'o (expected "c", actual "z")'
    )


def test_an_iri_value_is_shortened_by_the_spec_s_own_prefixes():
    from rdflib import Graph

    given = Graph().parse(
        data='@prefix ex: <https://example.org/> . ex:a ex:b ex:c .', format="ttl")
    df_diff = diff_of(
        {"s": ["https://example.org/sub"]},
        {"s": ["https://example.org/subject"]},
    )

    assert describe_differing_columns(df_diff, given.namespace_manager) == (
        "s (expected ex:sub, actual ex:subject)"
    )


def test_an_iri_value_with_no_prefix_to_hand_stays_a_full_iri():
    df_diff = diff_of(
        {"s": ["https://example.org/sub"]},
        {"s": ["https://example.org/subject"]},
    )

    assert describe_differing_columns(df_diff) == (
        "s (expected <https://example.org/sub>, actual <https://example.org/subject>)"
    )


def test_a_missing_cell_reads_as_empty():
    df_diff = diff_of({"o": ["one"]}, {"o": [""]})

    assert describe_differing_columns(df_diff) == 'o (expected "one", actual empty)'


def test_rows_disagreeing_on_values_fall_back_to_the_bare_name():
    df_diff = diff_of({"o": ["a", "b"]}, {"o": ["c", "d"]})

    assert describe_differing_columns(df_diff) == "o"


def test_a_long_value_is_elided():
    long_value = "x" * 100
    df_diff = diff_of({"o": [long_value]}, {"o": ["y"]})

    described = describe_differing_columns(df_diff)
    assert described == f'o (expected "{"x" * 60}…", actual "y")'


def test_a_column_that_does_not_actually_differ_is_left_out():
    # When the two tables have different shapes or column names the diff is
    # built side by side rather than by DataFrame.compare, so it carries the
    # matching columns too. "expected X, actual X" is worse than silence.
    df_diff = pandas.DataFrame({
        ("s", "expected"): ["same"], ("s", "actual"): ["same"],
        ("o", "expected"): ["one"], ("o", "actual"): ["two"],
    })

    assert describe_differing_columns(df_diff) == 'o (expected "one", actual "two")'


def test_many_differing_columns_fall_back_to_bare_names():
    # Past a readable length the line has stopped being a summary, and the diff
    # table is the right tool.
    wide_expected = {f"c{i}": [f"expected-value-number-{i}"] for i in range(8)}
    wide_actual = {f"c{i}": [f"actual-value-number-{i}"] for i in range(8)}
    df_diff = diff_of(wide_expected, wide_actual)

    assert describe_differing_columns(df_diff) == "c0, c1, c2, c3, c4, c5, c6, c7"


@pytest.mark.parametrize("not_a_diff", [None, pandas.DataFrame()])
def test_describe_tolerates_nothing_to_describe(not_a_diff):
    assert describe_differing_columns(not_a_diff) == ""
