from mustrd.mustrdQueryProcessor import MustrdQueryProcessor
from datetime import datetime
from rdflib.plugins.sparql.parser import parseQuery, parseUpdate


query = """
PREFIX test: <http://test.com/>
SELECT *
WHERE {
    ?s test:p ?o ;
    <urn:p2> ?o1
    {
        ?s test:p3 ?o ;
    } UNION {
        ?s <urn:p4> ?o ;
    }
    ?o <urn:p5> ?obj .
    OPTIONAL {
        ?obj <urn:p5> ?jj
    }
    FILTER NOT EXISTS {
        ?obj <urn:p6> ?jj
    }
    BIND(LANG(?jj) as ?lang)
    FILTER((isNumeric(?o) && ?o > 4) || isIRI(?o))
    {
        SELECT * WHERE {
            ?s <urn:a> ?o1
            {
                ?s <urn:b> ?o2
            } UNION {
                ?s <urn:c> ?o3
            }
        }
    }
        
} 
"""

def test_mustrd_processor_graph_mode_on():
    proc = MustrdQueryProcessor(query, True)
    
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
    #graph_str = proc.serialize_graph()
    #print(graph_str)
    
    proc.update(change_prefix)
    proc.update(change_variable)
    
    #graph_str = proc.serialize_graph()
    #print(graph_str)
    
    modified_query = proc.get_query()
    print(modified_query)
    
def test_mustrd_processor_graph_mode_off():
    proc = MustrdQueryProcessor(query, False)
    
    
    modified_query = proc.get_query()
    print(modified_query)
    