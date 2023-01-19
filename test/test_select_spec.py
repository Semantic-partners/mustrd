from rdflib.namespace import Namespace
from namespace import MUST
from mustrdRdfLib import MustrdRdfLib

from mustrd import  SpecPassed, SparqlParseFailure, execute_when, Spec_component, SelectSpecFailure

TEST_DATA = Namespace("https://semanticpartners.com/data/test/")

class TestRunSelectSpec:
    def test_select_spec_passes(self):
        given =Spec_component()
        when = Spec_component()
        then = Spec_component()

        given.value = "<https://semanticpartners.com/data/test/sub> <https://semanticpartners.com/data/test/pred> <https://semanticpartners.com/data/test/obj>  ."

        when.value = "select ?s ?p ?o { ?s ?p ?o }"
        when.queryType = MUST.SelectSparql

        then.value = """s,s_datatype,p,p_datatype,o,o_datatype
https://semanticpartners.com/data/test/sub,http://www.w3.org/2001/XMLSchema#anyURI,https://semanticpartners.com/data/test/pred,http://www.w3.org/2001/XMLSchema#anyURI,https://semanticpartners.com/data/test/obj,http://www.w3.org/2001/XMLSchema#anyURI"""
        spec_uri = TEST_DATA.my_first_spec

        actual_status = execute_when(when, given, then, spec_uri, MustrdRdfLib())
        assert type(actual_status) == SpecPassed

    def test_select_spec_fails_with_expected_vs_actual_table_comparison(self):
        given =Spec_component()
        when = Spec_component()
        then = Spec_component()

        given.value = "<https://semanticpartners.com/data/test/sub> <https://semanticpartners.com/data/test/pred> <https://semanticpartners.com/data/test/obj> ."

        when.value = "select ?s ?p ?o { ?s ?p ?o }"
        when.queryType = MUST.SelectSparql

        then.value = """s,s_datatype,p,p_datatype,o,o_datatype
https://semanticpartners.com/data/test/wrong-subject,http://www.w3.org/2001/XMLSchema#anyURI,https://semanticpartners.com/data/test/pred,http://www.w3.org/2001/XMLSchema#anyURI,https://semanticpartners.com/data/test/obj,http://www.w3.org/2001/XMLSchema#anyURI"""
        spec_uri = TEST_DATA.my_first_spec

        actual_status = execute_when(when, given, then, spec_uri, MustrdRdfLib())

        assert type(actual_status) == SelectSpecFailure
        table_diff = actual_status.table_comparison.to_markdown()
        assert actual_status.spec_uri == spec_uri
        assert table_diff == """|    | ('s', 'expected')                                    | ('s', 'actual')                            |
|---:|:-----------------------------------------------------|:-------------------------------------------|
|  0 | https://semanticpartners.com/data/test/wrong-subject | https://semanticpartners.com/data/test/sub |"""

    def test_select_spec_fails_for_different_types(self):
        given =Spec_component()
        when = Spec_component()
        then = Spec_component()
        given.value = "<https://semanticpartners.com/data/test/sub> <https://semanticpartners.com/data/test/pred> 1 ."
        when.value = "select ?s ?p ?o { ?s ?p ?o }"
        when.queryType = MUST.SelectSparql

        then.value = """s,s_datatype,p,p_datatype,o,o_datatype
https://semanticpartners.com/data/test/sub,http://www.w3.org/2001/XMLSchema#anyURI,https://semanticpartners.com/data/test/pred,http://www.w3.org/2001/XMLSchema#anyURI,1.0,http://www.w3.org/2001/XMLSchema#decimal"""
        spec_uri = TEST_DATA.my_first_spec

        actual_status = execute_when(when, given, then, spec_uri, MustrdRdfLib())

        assert type(actual_status) == SelectSpecFailure
        table_diff = actual_status.table_comparison.to_markdown()
        assert actual_status.spec_uri == spec_uri
        assert table_diff == """|    |   ('o', 'expected') |   ('o', 'actual') | ('o_datatype', 'expected')               | ('o_datatype', 'actual')                 |
|---:|--------------------:|------------------:|:-----------------------------------------|:-----------------------------------------|
|  0 |                   1 |                 1 | http://www.w3.org/2001/XMLSchema#decimal | http://www.w3.org/2001/XMLSchema#integer |"""

    def test_select_spec_fails_for_different_types_where_one_is_string(self):
        given =Spec_component()
        when = Spec_component()
        then = Spec_component()

        given.value = "<https://semanticpartners.com/data/test/sub> <https://semanticpartners.com/data/test/pred> 1 ."
        when.value = "select ?s ?p ?o { ?s ?p ?o }"
        when.queryType = MUST.SelectSparql

        then.value = """s,s_datatype,p,p_datatype,o,o_datatype
https://semanticpartners.com/data/test/sub,http://www.w3.org/2001/XMLSchema#anyURI,https://semanticpartners.com/data/test/pred,http://www.w3.org/2001/XMLSchema#anyURI,1,http://www.w3.org/2001/XMLSchema#string"""
        spec_uri = TEST_DATA.my_first_spec

        actual_status = execute_when(when, given, then, spec_uri, MustrdRdfLib())

        assert type(actual_status) == SelectSpecFailure
        table_diff = actual_status.table_comparison.to_markdown()
        assert actual_status.spec_uri == spec_uri
        assert table_diff == """|    |   ('o', 'expected') |   ('o', 'actual') | ('o_datatype', 'expected')              | ('o_datatype', 'actual')                 |
|---:|--------------------:|------------------:|:----------------------------------------|:-----------------------------------------|
|  0 |                   1 |                 1 | http://www.w3.org/2001/XMLSchema#string | http://www.w3.org/2001/XMLSchema#integer |"""

    def test_invalid_select_statement_spec_fails(self):
        given =Spec_component()
        when = Spec_component()
        then = Spec_component()
        
        given.value = "<https://semanticpartners.com/data/test/sub> <https://semanticpartners.com/data/test/pred> <https://semanticpartners.com/data/test/obj> ."

        when.value = "select ?s ?p ?o { typo }"
        when.queryType = MUST.SelectSparql

        then.value = """s,s_datatype,p,p_datatype,o,o_datatype
https://semanticpartners.com/data/test/sub,http://www.w3.org/2001/XMLSchema#anyURI,https://semanticpartners.com/data/test/pred,http://www.w3.org/2001/XMLSchema#anyURI,https://semanticpartners.com/data/test/obj,http://www.w3.org/2001/XMLSchema#anyURI"""
        spec_uri = TEST_DATA.my_first_spec

        actual_status = execute_when(when, given, then, spec_uri, MustrdRdfLib())

        assert type(actual_status) == SparqlParseFailure
        assert actual_status.spec_uri == spec_uri
        assert str(actual_status.exception) == "Expected {SelectQuery | ConstructQuery | DescribeQuery | AskQuery}, found 'typo'  (at char 18), (line:1, col:19)"
