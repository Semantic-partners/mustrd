"""The "Queried" headline, and term coverage without running the tests.

A spec that reads an existing store (must:InheritedDataset) has no input data, so
it can never move "Overall". "Queried" counts the declared terms a passing spec's
query names, so such a suite still reports what its queries reach.
"""
import re

import pytest
from rdflib import Graph

from mustrd.cli import main
from mustrd.coverage import compute_coverage
from mustrd.mustrdTestPlugin import MustrdTestPlugin
from mustrd.reporting import ReportOptions
from mustrd.runner import collect_specs, static_coverage

ONTO = """
@prefix onto: <http://onto.org/> .
@prefix owl:  <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
onto:Place a owl:Class .
onto:City a owl:Class ; rdfs:subClassOf onto:Place .
onto:Country a owl:Class ; rdfs:subClassOf onto:Place .
onto:isLocatedIn a owl:ObjectProperty ;
    rdfs:domain onto:Place ; rdfs:range onto:Place .
"""

# Names a declared class, a declared property, and RDFS/OWL vocabulary.
QUERY = """
PREFIX onto: <http://onto.org/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?x WHERE { ?x a onto:City ; onto:isLocatedIn ?y . ?c rdfs:subClassOf ?d . }
"""

OVERALL = re.compile(r"\*\*Overall:\s*([^*\n]+)\*\*")
QUERIED = re.compile(r"\*\*Queried:\s*([^*\n]+)\*\*")


def _ontology():
    return Graph().parse(data=ONTO, format="turtle")


def _spec(passed=True, queries=(), name="a.mustrd.ttl"):
    return {"name": name, "uri": f"http://ex/{name}", "passed": passed,
            "given": None, "queries": list(queries)}


def test_a_query_with_no_given_counts_as_queried_not_covered():
    cov = compute_coverage([_spec(queries=[QUERY])], ontology=_ontology())
    assert cov["queried"] == 2          # onto:City, onto:isLocatedIn
    assert cov["covered"] == 0
    assert cov["queried_pct"] == round(100 * 2 / cov["denominator"])


def test_structural_terms_are_not_counted_as_queried():
    # onto:Place is structural (superclass of City, domain/range of isLocatedIn)
    # and the query's rdfs:subClassOf is not a declared term: neither counts.
    cov = compute_coverage([_spec(queries=[QUERY])], ontology=_ontology())
    assert cov["schema_count"] == 1
    assert cov["denominator"] == 3      # City, Country, isLocatedIn
    assert cov["queried"] == 2
    structural = {r["iri"] for r in cov["term_records"] if r["role"] == "schema"}
    assert structural == {"http://onto.org/Place"}


def test_a_failing_specs_query_terms_are_not_queried():
    cov = compute_coverage([_spec(passed=False, queries=[QUERY])], ontology=_ontology())
    assert cov["queried"] == 0


def test_queried_counts_terms_also_in_input_data():
    given = Graph().parse(data="""
        @prefix onto: <http://onto.org/> .
        <http://ex/r> a onto:City .""", format="turtle")
    spec = {**_spec(queries=[QUERY]), "given": given}
    cov = compute_coverage([spec], ontology=_ontology())
    assert cov["covered"] == 1          # City, in data
    assert cov["queried"] == 2          # City and isLocatedIn, by the query


# --- an InheritedDataset-only suite --------------------------------------------

CITY_QUERY = ("PREFIX onto: <http://onto.org/> "
              "SELECT ?x WHERE { ?x a onto:City ; onto:isLocatedIn ?y }")

SPEC = f"""
@prefix must: <https://mustrd.org/model/> .
@prefix ex:   <http://ex/> .
ex:inheritedCities
    a          must:TestSpec ;
    must:given [ a must:InheritedDataset ] ;
    must:when  [ a must:TextSparqlSource ;
                 must:queryText "{CITY_QUERY}" ;
                 must:queryType must:SelectSparql ] ;
    must:then  [ a must:EmptyTable ] .
"""

# rdflib cannot run an inherited-state spec (run_spec reports it invalid), so the
# pytest path uses the nearest runnable shape: input data that names no ontology
# term, which leaves Overall at zero just as an inherited store would.
RUNNABLE_SPEC = f"""
@prefix must: <https://mustrd.org/model/> .
@prefix ex:   <http://ex/> .
ex:queryOnlyCities
    a          must:TestSpec ;
    must:given [ a must:StatementsDataset ;
                 must:hasStatement [ a rdf:Statement ;
                     rdf:subject ex:s ; rdf:predicate ex:p ; rdf:object ex:o ] ] ;
    must:when  [ a must:TextSparqlSource ;
                 must:queryText "{CITY_QUERY}" ;
                 must:queryType must:SelectSparql ] ;
    must:then  [ a must:EmptyTable ] .
"""

CONFIG = """
@prefix :            <https://mustrd.org/mustrdTest/> .
@prefix triplestore: <https://mustrd.org/triplestore/> .
:inherited a :MustrdTest ;
    :hasSpecPath     "specs" ;
    :hasDataPath     "data" ;
    :hasOntologyPath "onto.ttl" ;
    :hasPytestPath   "inherited" ;
    :filterOnTripleStore triplestore:RdfLib .
"""


@pytest.fixture
def inherited_suite(tmp_path, monkeypatch):
    (tmp_path / "specs").mkdir()
    (tmp_path / "data").mkdir()
    (tmp_path / "specs" / "inherited.mustrd.ttl").write_text(SPEC, encoding="utf-8")
    (tmp_path / "onto.ttl").write_text(ONTO, encoding="utf-8")
    (tmp_path / "mustrd-config.ttl").write_text(CONFIG, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _headlines(md_text):
    return OVERALL.search(md_text).group(1), QUERIED.search(md_text).group(1)


def test_pytest_run_reports_queried_when_input_data_names_no_term(inherited_suite):
    (inherited_suite / "specs" / "inherited.mustrd.ttl").write_text(
        "@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .\n" + RUNNABLE_SPEC,
        encoding="utf-8")
    md = inherited_suite / "out.md"
    plugin = MustrdTestPlugin(str(md), inherited_suite / "mustrd-config.ttl", None,
                              term_coverage=True)
    assert pytest.main([".", "-p", "no:cacheprovider", "-q"], plugins=[plugin]) == 0
    overall, queried = _headlines(md.read_text(encoding="utf-8"))
    assert overall == "0/3 terms exercised by the tests = 0%"
    assert queried == "2/3 terms named by a query = 67%"


def test_cli_coverage_command_runs_no_spec(inherited_suite, monkeypatch):
    import mustrd.runner
    monkeypatch.setattr(mustrd.runner, "run_spec",
                        lambda spec: pytest.fail("coverage must not run a spec"))
    md = inherited_suite / "cov.md"
    assert main(["coverage", "--config", "mustrd-config.ttl", "--md", str(md)]) == 0
    overall, queried = _headlines(md.read_text(encoding="utf-8"))
    assert overall == "0/3 terms exercised by the tests = 0%"
    assert queried == "2/3 terms named by a query = 67%"


def test_static_coverage_is_callable_as_a_library(inherited_suite, monkeypatch):
    import mustrd.runner
    monkeypatch.setattr(mustrd.runner, "run_spec",
                        lambda spec: pytest.fail("coverage must not run a spec"))
    cov = static_coverage("mustrd-config.ttl")
    assert (cov["covered"], cov["queried"], cov["denominator"]) == (0, 2, 3)

    specs, by_uri, _ = collect_specs("mustrd-config.ttl")
    assert [s["passed"] for s in specs] == [True]
    assert "http://ex/inheritedCities" in by_uri


def test_static_coverage_honours_report_options(inherited_suite):
    ttl = inherited_suite / "cov.ttl"
    static_coverage("mustrd-config.ttl", ReportOptions(term_coverage_rdf=str(ttl)))
    g = Graph().parse(ttl, format="turtle")
    q = """PREFIX dqv: <http://www.w3.org/ns/dqv#>
           PREFIX cov: <https://mustrd.org/coverage/>
           SELECT ?v WHERE { ?m dqv:isMeasurementOf cov:termCoverageByQueries ;
                                dqv:value ?v }"""
    assert [float(r.v) for r in g.query(q)] == [0.6667]
