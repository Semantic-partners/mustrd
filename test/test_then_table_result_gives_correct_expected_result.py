import pandas
from rdflib import Graph, XSD
from rdflib.namespace import Namespace
from rdflib.term import Literal
from mustrd.namespace import MUST, TRIPLESTORE

TEST_DATA = Namespace("https://semanticpartners.com/data/test/")


class TestRunSelectSpec:

    triple_store = {"type": TRIPLESTORE.RdfLib}

    def test_select_spec_fails_with_expected_vs_actual_table_comparison(self):

        spec = """
        @prefix rdf:       <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
        @prefix sh:        <http://www.w3.org/ns/shacl#> .
        @prefix must:      <https://mustrd.org/model/> .
        @prefix test-data: <https://semanticpartners.com/data/test/> .

            test-data:my_failing_spec
                 a          must:TestSpec ;
    must:then  [ a must:TableDataset ;
                 must:hasRow
                  [ must:hasBinding [ must:variable "s" ;
                                         must:boundValue  test-data:sub2 ; ],
                                       [ must:variable "o" ;
                                         must:boundValue  test-data:obj ; ]; ] ,
                  [ must:hasBinding
                                       [ must:variable "s" ;
                                         must:boundValue  test-data:sub1 ; ],
                                       [ must:variable "o" ;
                                         must:boundValue  test-data:obj ; ] ,
                                       [ must:variable "object" ;
                                         must:boundValue  test-data:object ; ] ; ] ;

               ] .
            """
        spec_graph = Graph().parse(data=spec, format='ttl')
        subject = TEST_DATA.my_failing_spec
        predicate = MUST.then

        then_query = f"""
        prefix sh:        <http://www.w3.org/ns/shacl#>
            SELECT ?row ?variable ?binding ?order
            WHERE {{
                 <{subject}> <{predicate}> [
                        a <{MUST.TableDataset}> ;
                        <{MUST.hasRow}> ?row ].
                          ?row  <{MUST.hasBinding}> [
                                <{MUST.variable}> ?variable ;
                                <{MUST.boundValue}> ?binding ; ] .
                          OPTIONAL {{ ?row sh:order ?order . }}
                                     .}}
             ORDER BY ?row ?order"""

        expected_results = spec_graph.query(then_query)
        index = {str(row.row) for row in expected_results}
        columns = set()
        for row in expected_results:
            columns.add(row.variable.value)
            columns.add(row.variable.value + "_datatype")
        df = pandas.DataFrame(index=list(index), columns=list(columns))
        for row in expected_results:
            df.loc[str(row.row), row.variable.value] = str(row.binding)
            if isinstance(row.binding, Literal):
                literal_type = str(XSD.string)
                if hasattr(row.binding, "datatype") and row.binding.datatype:
                    literal_type = str(row.binding.datatype)
                df.loc[str(row.row), row.variable.value + "_datatype"] = literal_type
            else:
                df.loc[str(row.row), row.variable.value + "_datatype"] = str(XSD.anyURI)
        df.reset_index(drop=True, inplace=True)
        df.fillna('', inplace=True)
