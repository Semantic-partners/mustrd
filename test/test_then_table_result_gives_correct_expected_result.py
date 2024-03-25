"""
MIT License

Copyright (c) 2023 Semantic Partners Ltd

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""


import pandas
from rdflib import Graph, XSD
from rdflib.namespace import Namespace
from rdflib.term import Literal
from mustrd.namespace import MUST

TEST_DATA = Namespace("https://semanticpartners.com/data/test/")


class TestRunSelectSpec:

    triple_store = {"type": MUST.RdfLib}
    def test_select_spec_fails_with_expected_vs_actual_table_comparison(self):

        spec = """
        @prefix rdf:       <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
        @prefix sh:        <http://www.w3.org/ns/shacl#> .
        @prefix must:      <https://mustrd.com/model/> .
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
        spec_graph= Graph().parse(data=spec, format='ttl')
        subject = TEST_DATA.my_failing_spec
        predicate = MUST.then
        # addspec_source_file_to_spec_graph(spec_graph, spec_uri, __name__)

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
            if type(row.binding) == Literal:
                literal_type = str(XSD.string)
                if hasattr(row.binding, "datatype") and row.binding.datatype:
                    literal_type = str(row.binding.datatype)
                df.loc[str(row.row), row.variable.value + "_datatype"] = literal_type
            else:
                df.loc[str(row.row), row.variable.value + "_datatype"] = str(XSD.anyURI)
        df.reset_index(drop=True, inplace=True)
        df.fillna('', inplace=True)

        print(df.to_string())
        # df.groupby('Row').apply(lambda x: join(x.astype(str)))
        # print(then_component.value.to_string())
        # remove = string.whitespace
        # mapping = {ord(c): None for c in remove}
        expected_result = '''                                             s                               s_datatype                                           o                               o_datatype                                         object                          object_datatype
0  https://semanticpartners.com/data/test/sub1  http://www.w3.org/2001/XMLSchema#anyURI  https://semanticpartners.com/data/test/obj  http://www.w3.org/2001/XMLSchema#anyURI  https://semanticpartners.com/data/test/object  http://www.w3.org/2001/XMLSchema#anyURI
1  https://semanticpartners.com/data/test/sub2  http://www.w3.org/2001/XMLSchema#anyURI  https://semanticpartners.com/data/test/obj  http://www.w3.org/2001/XMLSchema#anyURI                                                                                        '''

