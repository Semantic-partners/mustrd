import unittest
import tempfile
import os
import unittest
from rdflib import Graph, Literal, URIRef, RDF

from mustrd import get_credential_from_file, get_triple_stores
from namespace import MUST


class TestGetCredentialFromFile(unittest.TestCase):
    def setUp(self):
        # Create a temporary config file for testing
        self.config_file = tempfile.NamedTemporaryFile(delete=False)
        self.config_file.write(b"[triple_store_name]\nusername=test_user\npassword=test_password\n")
        self.config_file.close()

    def tearDown(self):
        # Remove the temporary config file
        os.remove(self.config_file.name)

    def test_get_credential_from_file(self):
        triple_store_name = "triple_store_name"
        credential = "username"
        config_path = self.config_file.name
        result = get_credential_from_file(triple_store_name, credential, config_path)
        expected = "test_user"
        self.assertEqual(result, expected)

    def test_get_credential_from_file_missing_parameter(self):
        triple_store_name = "triple_store_name"
        credential = "username"
        config_path = None
        with self.assertRaises(ValueError):
            get_credential_from_file(triple_store_name, credential, config_path)

    def test_get_credential_from_file_missing_file(self):
        triple_store_name = "triple_store_name"
        credential = "username"
        config_path = "nonexistent_file.ini"
        with self.assertRaises(FileNotFoundError):
            get_credential_from_file(triple_store_name, credential, config_path)

    def test_get_credential_from_file_invalid_config_file(self):
        triple_store_name = "triple_store_name"
        credential = "username"
        config_path = self.config_file.name
        with open(config_path, "w") as f:
            f.write("invalid config")
        with self.assertRaises(ValueError):
            get_credential_from_file(triple_store_name, credential, config_path)


class TestGetTripleStores(unittest.TestCase):
    def setUp(self):
        # Create a temporary config file for testing
        self.config_file = tempfile.NamedTemporaryFile(delete=False)
        self.config_file = tempfile.NamedTemporaryFile(delete=False)
        self.config_file.write(
            b"[https://mustrd.com/model/AnzoConfig1]\nusername=test_user\npassword=test_password\n\n")
        self.config_file.write(
            b"[https://mustrd.com/model/GraphDbConfig1]\nusername=test_user\npassword=test_password\n\n")
        self.config_file.close()

    def tearDown(self):
        # Remove the temporary config file
        os.remove(self.config_file.name)

    def test_get_triple_stores_with_rdflib(self):
        triple_store_graph = Graph()
        rdf_type = URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")
        triple_store_type = MUST.RdfLibConfig
        triple_store_graph.add((URIRef("http://example.org/rdflib-store"), rdf_type, triple_store_type))

        triple_stores = get_triple_stores(triple_store_graph)

        self.assertEqual(len(triple_stores), 1)
        self.assertEqual(triple_stores[0]["type"], MUST.RdfLib)

    def test_get_triple_stores_with_anzo(self):
        triple_store_graph = Graph()
        rdf_type = URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")
        triple_store_type = MUST.AnzoConfig
        triple_store_uri = URIRef("https://mustrd.com/model/AnzoConfig1")
        triple_store_graph.add((triple_store_uri, rdf_type, triple_store_type))
        triple_store_graph.add((triple_store_uri, MUST.url, Literal("http://example.com/anzo")))
        triple_store_graph.add((triple_store_uri, MUST.port, Literal(8080)))
        triple_store_graph.add((triple_store_uri, MUST.username, Literal(f"{self.config_file.name}")))
        triple_store_graph.add((triple_store_uri, MUST.password, Literal(f"{self.config_file.name}")))
        triple_store_graph.add((triple_store_uri, MUST.gqeURI, Literal("http://example.com/gqe")))
        triple_store_graph.add((triple_store_uri, MUST.inputGraph, Literal("http://example.com/input-graph")))

        triple_stores = get_triple_stores(triple_store_graph)

        self.assertEqual(len(triple_stores), 1)
        self.assertEqual(triple_stores[0]["type"], MUST.Anzo)
        self.assertEqual(triple_stores[0]["url"], Literal("http://example.com/anzo"))
        self.assertEqual(triple_stores[0]["port"], Literal(8080))
        self.assertEqual(triple_stores[0]["username"], "test_user")
        self.assertEqual(triple_stores[0]["password"], "test_password")
        self.assertEqual(triple_stores[0]["gqe_uri"], Literal("http://example.com/gqe"))
        self.assertEqual(triple_stores[0]["input_graph"], Literal("http://example.com/input-graph"))

    def test_get_triple_stores_with_graphdb(self):
        triple_store_graph = Graph()
        rdf_type = URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")
        triple_store_type = MUST.GraphDbConfig
        triple_store_uri = URIRef("https://mustrd.com/model/GraphDbConfig1")
        triple_store_graph.add((triple_store_uri, rdf_type, triple_store_type))
        triple_store_graph.add((triple_store_uri, MUST.url, Literal("http://example.com/graphdb")))
        triple_store_graph.add((triple_store_uri, MUST.port, Literal(8080)))
        triple_store_graph.add((triple_store_uri, MUST.username, Literal(f"{self.config_file.name}")))
        triple_store_graph.add((triple_store_uri, MUST.password, Literal(f"{self.config_file.name}")))
        triple_store_graph.add((triple_store_uri, MUST.repository, Literal("Test")))
        triple_store_graph.add((triple_store_uri, MUST.inputGraph, Literal("http://example.com/input-graph")))

        triple_stores = get_triple_stores(triple_store_graph)

        self.assertEqual(len(triple_stores), 1)
        self.assertEqual(triple_stores[0]["type"], MUST.GraphDb)
        self.assertEqual(triple_stores[0]["url"], Literal("http://example.com/graphdb"))
        self.assertEqual(triple_stores[0]["port"], Literal(8080))
        self.assertEqual(triple_stores[0]["username"], "test_user")
        self.assertEqual(triple_stores[0]["password"], "test_password")
        self.assertEqual(triple_stores[0]["repository"], Literal("Test"))
        self.assertEqual(triple_stores[0]["input_graph"], Literal("http://example.com/input-graph"))

    def test_unsupported_triple_store_type(self):
        # create a test graph with an unsupported triple store type
        graph = Graph()
        config_uri = URIRef("http://example.com/config")
        graph.add((config_uri, RDF.type, URIRef("http://example.com/unsupported_type")))

        # call the function and check that the error message is returned
        triple_stores = get_triple_stores(graph)
        self.assertEqual(len(triple_stores), 1)
        self.assertIn("error", triple_stores[0])
        self.assertIn("Triple store not implemented", triple_stores[0]["error"])
