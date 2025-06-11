import pytest
from rdflib import Graph, URIRef
from mustrd.steprunner import _spade_edn_group_source
from mustrd.namespace import MUST, TRIPLESTORE
from mustrd.spec_component import SpadeEdnGroupSourceWhenSpec, WhenSpec

def test_spade_edn_group_source():
    # Mock triple store and spec_uri
    triple_store = {
        "type": TRIPLESTORE.RdfLib,
        "given": Graph()
    }
    spec_uri = URIRef("http://example.com/test-spec")
    
    # Add sample RDF data to the given graph
    triples = """
    @prefix test-data: <https://semanticpartners.com/data/test/> .
    test-data:sub test-data:pred test-data:obj .
    """
    triple_store["given"].parse(data=triples, format="ttl")
    

    edn_file_path = "./test/data/test_spade_edn.edn"
    # Create a temporary EDN file
    edn_content = """
    {:step-groups [
        {:steps [
            {:type :sparql-file, :filepath "./test/data/insert.rq"}
        ]}
    ]}
    """
    with open(edn_file_path, "w") as edn_file:
        edn_file.write(edn_content)

    # Mock WhenSpec
    when_spec = SpadeEdnGroupSourceWhenSpec(
        file=edn_file_path,
        groupId="group-1",
        queryType=MUST.UpdateSparql,  # Assume a UpdateSparql query type for this test
        value=[
            WhenSpec(
                queryType=MUST.UpdateSparql,
                value="insert { ?o ?s ?p } where { ?s ?p ?o }"
            )
        ]
    )

   
    
    # Run the method
    result = _spade_edn_group_source(spec_uri, triple_store, when_spec)
    

    
    print(result.serialize(format="nt").decode("utf-8") if hasattr(result.serialize(format="nt"), "decode") else result.serialize(format="nt"))
    # Assert the result
    # Serialize the first graph in result to n-triples and compare with expected
    expected_nt = "<https://semanticpartners.com/data/test/obj> <https://semanticpartners.com/data/test/sub> <https://semanticpartners.com/data/test/pred> .\n"
    
    actual_nt = result.serialize(format="nt")
    if hasattr(actual_nt, "decode"):
        actual_nt = actual_nt.decode("utf-8")
    assert expected_nt in actual_nt

    # Clean up temporary file
    import os
    os.remove(edn_file_path)

if __name__ == "__main__":
    pytest.main(["-v", "test_spade_edn_group_source.py"])
