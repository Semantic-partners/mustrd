"""Turn a SELECT into ASK queries, so a check runs in the store and only a
boolean comes back.

The SELECT is not rewritten: it goes inside the ASK unchanged, as a subquery.
Projection expressions, aggregates, GROUP BY, ORDER BY, LIMIT and a trailing
VALUES all keep their meaning. Two parts of a query are not allowed in a
subquery, so they move to the outer ASK:

- the prologue (BASE and PREFIX declarations);
- the dataset clauses (FROM and FROM NAMED).

Finding those needs to know where strings, IRIs and comments are, so a keyword
inside one is not mistaken for the real thing. `split_select` does that with a
small scanner rather than a regular expression over the whole text.
"""
import re
from dataclasses import dataclass
from typing import List, Optional, Sequence

# SPARQL's own IRIREF rule: no spaces, so `?a < ?b` is never read as an IRI.
_IRIREF = re.compile(r'<[^<>"{}|^`\\\x00-\x20]*>')
_LONG_STRING = re.compile(r'"""(?:[^"\\]|\\.|"(?!""))*"""|\'\'\'(?:[^\'\\]|\\.|\'(?!\'\'))*\'\'\'', re.S)
_STRING = re.compile(r'"(?:[^"\\\n]|\\.)*"|\'(?:[^\'\\\n]|\\.)*\'')
_WORD = re.compile(r'[A-Za-z_][A-Za-z0-9_-]*')
_PREFIXED_OR_IRI = re.compile(r'\s*(<[^<>"{}|^`\\\x00-\x20]*>|[A-Za-z0-9_.-]*:[^\s{}()]*)')


@dataclass(frozen=True)
class SelectParts:
    prologue: str      # BASE / PREFIX declarations, as written
    dataset: str       # FROM / FROM NAMED clauses, as written
    query: str         # the SELECT with its dataset clauses taken out


def _top_level_words(text: str):
    """(word in upper case, start, end, depth) for each bare word, and each `{`,
    outside strings, IRIs and comments. Depth counts open braces and parentheses
    before the token."""
    i, depth = 0, 0
    while i < len(text):
        c = text[i]
        if c == "#":
            end = text.find("\n", i)
            i = len(text) if end == -1 else end
            continue
        if c in "\"'":
            m = _LONG_STRING.match(text, i) or _STRING.match(text, i)
            i = m.end() if m else i + 1
            continue
        if c == "<":
            m = _IRIREF.match(text, i)
            i = m.end() if m else i + 1
            continue
        if c == "{":
            yield "{", i, i + 1, depth
        if c in "{(":
            depth += 1
        elif c in "})":
            depth -= 1
        elif c in "?$":
            # a variable: skip its name so `?select` is not the keyword
            m = _WORD.match(text, i + 1)
            i = m.end() if m else i + 1
            continue
        elif c.isalpha() or c == "_":
            m = _WORD.match(text, i)
            end = m.end()
            # A prefixed name (`ex:select`, `select:x`) is not a keyword.
            prefixed = (end < len(text) and text[end] == ":") or (i > 0 and text[i - 1] == ":")
            if not prefixed:
                yield m.group().upper(), i, end, depth
            i = end
            continue
        i += 1


def split_select(query: str) -> SelectParts:
    """The prologue, dataset clauses and body of a SELECT query.

    Raises ValueError if the text is not a SELECT."""
    words = list(_top_level_words(query))
    select = next((w for w in words if w[0] == "SELECT" and w[3] == 0), None)
    if select is None:
        raise ValueError("Only a SELECT query can be checked with must:AskConditions")
    prologue = query[:select[1]]

    # Dataset clauses sit between the projection and the WHERE clause: FROM is
    # only ever a keyword at depth 0 there, and the first `{` ends the search.
    body_start = select[1]
    froms = []
    for word, start, end, depth in words:
        if start < select[2] or depth != 0:
            continue
        if word == "{":
            break
        if word == "FROM":
            cursor = end
            named = re.match(r"\s*NAMED\b", query[cursor:], re.I)
            if named:
                cursor += named.end()
            target = _PREFIXED_OR_IRI.match(query, cursor)
            if not target:
                raise ValueError(f"Could not read the FROM clause at offset {start}")
            froms.append((start, target.end()))

    dataset = " ".join(query[s:e].strip() for s, e in froms)
    body = query[body_start:]
    for s, e in reversed(froms):
        body = body[:s - body_start] + body[e - body_start:]
    return SelectParts(prologue=prologue, dataset=dataset, query=body.strip())


def inline_bindings(select: str, bindings: Optional[dict]) -> str:
    """The SELECT with each binding as a VALUES block at the top of its WHERE.

    Done before wrapping, not left to the store. Stores apply bindings to the
    query they are sent, and once the SELECT is a subquery a binding at the outer
    level cannot reach a variable the SELECT does not project."""
    if not bindings:
        return select
    select_word = next((w for w in _top_level_words(select) if w[0] == "SELECT" and w[3] == 0), None)
    if select_word is None:
        raise ValueError("Only a SELECT query can be checked with must:AskConditions")
    where_open = next((w for w in _top_level_words(select)
                       if w[0] == "{" and w[3] == 0 and w[1] > select_word[2]), None)
    if where_open is None:
        raise ValueError("No WHERE clause found in the query to bind values to.")
    values = "".join(f"\nVALUES ?{name} {{ {value.n3()} }}" for name, value in bindings.items())
    return select[:where_open[2]] + values + select[where_open[2]:]


@dataclass(frozen=True)
class Condition:
    """A SPARQL expression over the SELECT's projected variables."""
    expression: str
    every_row: bool = True


def _ask(parts: SelectParts, where: str) -> str:
    dataset = f"{parts.dataset}\n" if parts.dataset else ""
    return f"{parts.prologue}ASK\n{dataset}WHERE {{\n{where}\n}}"


def _sub(parts: SelectParts) -> str:
    return "{\n" + parts.query + "\n}"


def ask_for_row_count(select: str, min_rows: int = 1, max_rows: Optional[int] = None) -> str:
    """An ASK that is true when the SELECT returns between min_rows and max_rows rows."""
    parts = split_select(select)
    bounds = [f"?mustrd_rows >= {int(min_rows)}"]
    if max_rows is not None:
        bounds.append(f"?mustrd_rows <= {int(max_rows)}")
    return _ask(parts, f"{{ SELECT (COUNT(*) AS ?mustrd_rows) WHERE {{ {_sub(parts)} }} }}\n"
                       f"FILTER ({' && '.join(bounds)})")


def ask_for_condition(select: str, condition: Condition) -> str:
    """An ASK that is true when the condition holds on every row (or some row).

    COALESCE turns an expression that errors — usually an unbound variable — into
    false. Without it, a row with no value would pass an every-row check, because
    FILTER drops the row instead of counting it as a failure.
    """
    parts = split_select(select)
    holds = f"COALESCE(({condition.expression}), false)"
    if condition.every_row:
        return _ask(parts, f"FILTER NOT EXISTS {{ {_sub(parts)}\nFILTER (!{holds}) }}")
    return _ask(parts, f"{_sub(parts)}\nFILTER ({holds})")


@dataclass(frozen=True)
class AskCheck:
    """One ASK, and what to call it when it comes back false.

    The description is all a failure report shows, so it must not contain data
    from the store: describe the check, never the result."""
    description: str
    query: str


def describe_row_count(min_rows: int, max_rows: Optional[int]) -> str:
    if max_rows is None:
        return f"at least {min_rows} row{'' if min_rows == 1 else 's'}"
    if min_rows == max_rows:
        return f"exactly {min_rows} row{'' if min_rows == 1 else 's'}"
    return f"between {min_rows} and {max_rows} rows"


def describe_condition(condition: Condition) -> str:
    return f"{'every row' if condition.every_row else 'some row'}: {condition.expression}"


def subquery_rewriter(select: str, conditions: Sequence[Condition], min_rows: int = 1,
                      max_rows: Optional[int] = None) -> List[AskCheck]:
    """The row-count ASK followed by one ASK per condition."""
    return ([AskCheck(describe_row_count(min_rows, max_rows),
                      ask_for_row_count(select, min_rows, max_rows))]
            + [AskCheck(describe_condition(c), ask_for_condition(select, c))
               for c in conditions])
