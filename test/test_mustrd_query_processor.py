from mustrd.mustrdQueryProcessor import MustrdQueryProcessor
from datetime import datetime
from rdflib.plugins.sparql.parser import parseQuery, parseUpdate



def test_mustrd_algebra_processor():
    query = """
                PREFIX test: <http://test.com/>
                SELECT * FROM <http://mustrd.com/test> WHERE {
                    ?s test:p ?o
                }      
            """

    proc = MustrdQueryProcessor(query, False)
    res = proc.query("SELECT DISTINCT ?class WHERE {?s <https://mustrd.com/query/has_class> ?class}")
    
    change_prefix = """
        prefix ns1: <https://mustrd.com/query/>
        DELETE {
            ?s ns1:has_value "http://test.com/"
        } INSERT {
            ?s ns1:has_value "http://test2.com/"
        } WHERE {
            ?s ns1:has_value "http://test.com/"
        }
    """
    change_variable = """
        prefix ns1: <https://mustrd.com/query/>
        DELETE {
            ?s ns1:has_value "o"
        } INSERT {
            ?s ns1:has_value "object"
        } WHERE {
            ?s a ns1:Variable ;
            ns1:has_value "o"
        }
    """
    graph_str = proc.serialize()
    print(graph_str)
    
    proc.update(change_prefix)
    proc.update(change_variable)
    
    graph_str = proc.serialize()
    print(graph_str)
    
    query = proc.get_query()
    
    print(res)
    
def test_perf():
    query = """
            PREFIX test: <http://test.com/>
            SELECT * FROM <http://mustrd.com/test> WHERE {
                ?s test:p ?o .
                OPTIONAL {
                    ?s test:p2 ?o2;
                        test:p3 "bar", "foo";
                        test:p4 1 .
                }
                FILTER NOT EXISTS {
                    ?s test:p "foo" .
                }
                
            }      
        """
    t1 = datetime.now()
    proc = MustrdQueryProcessor(query, False)
    query = proc.get_query()
    print(f"Time: {str(datetime.now()-t1)}")

def test_perf2():
    query_str = """
        PREFIX test: <http://test.com/>
        SELECT * FROM <http://mustrd.com/test> WHERE {
            ?s test:p ?o .
            OPTIONAL {
                ?s test:p2 ?o2;
                    test:p3 "bar", "foo";
                    test:p4 1 .
            }
            FILTER NOT EXISTS {
                ?s test:p "foo" .
            }
            
        }      
    """
    t1 = datetime.now()
    parsetree = parseQuery(query_str)
    print(f"Time: {str(datetime.now()-t1)}")