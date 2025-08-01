import tempfile
import os
import unittest

import toml
from rdflib import Graph, Literal, URIRef, RDF

from mustrd.mustrd import get_credential_from_file, get_triple_stores
from mustrd.namespace import TRIPLESTORE


class TestGetCredentialFromFile(unittest.TestCase):
    def setUp(self):
        # Create a temporary config file for testing
        self.config_file = tempfile.NamedTemporaryFile(delete=False)
        config_data = {
            "triple_store_name": {
                "username": "test_user",
                "password": "test_password"
            }
        }
        self.config_file.write(toml.dumps(config_data).encode("utf-8"))
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

        config_data = {
            "https://mustrd.org/model/AnzoConfig1": {
                "username": "test_user",
                "password": "test_password"
            },
            "https://mustrd.org/model/GraphDbConfig1": {
                "username": "test_user",
                "password": "test_password"
            }
        }

        toml_data = toml.dumps(config_data)

        self.config_file.write(toml_data.encode("utf-8"))
        self.config_file.close()

    def tearDown(self):
        # Remove the temporary config file
        os.remove(self.config_file.name)

    def test_get_triple_stores_with_rdflib(self):
        triple_store_graph = Graph()
        rdf_type = URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")
        triple_store_type = TRIPLESTORE.RdfLib
        triple_store_graph.add((URIRef("http://example.org/rdflib-store"), rdf_type, triple_store_type))

        triple_stores = get_triple_stores(triple_store_graph)

        self.assertEqual(len(triple_stores), 1)
        self.assertEqual(triple_stores[0]["type"], TRIPLESTORE.RdfLib)

    def test_get_triple_stores_with_anzo(self):
        triple_store_graph = Graph()
        rdf_type = URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")
        triple_store_type = TRIPLESTORE.Anzo
        triple_store_uri = URIRef("https://mustrd.org/model/AnzoConfig1")
        triple_store_graph.add((triple_store_uri, rdf_type, triple_store_type))
        triple_store_graph.add((triple_store_uri, TRIPLESTORE.url, Literal("http://anzo.example.com:8080")))
        triple_store_graph.add((triple_store_uri, TRIPLESTORE.username, Literal("test_user")))
        triple_store_graph.add((triple_store_uri, TRIPLESTORE.password, Literal("test_password")))
        triple_store_graph.add((triple_store_uri, TRIPLESTORE.gqeURI, Literal("http://example.com/gqe")))
        triple_store_graph.add((triple_store_uri, TRIPLESTORE.inputGraph, Literal("http://example.com/input-graph")))
        triple_store_graph.add((triple_store_uri, TRIPLESTORE.outputGraph, Literal("http://example.com/output-graph")))

        triple_stores = get_triple_stores(triple_store_graph)

        self.assertEqual(len(triple_stores), 1)
        self.assertEqual(triple_stores[0]["type"], TRIPLESTORE.Anzo)
        self.assertEqual(triple_stores[0]["url"], Literal("http://anzo.example.com:8080"))
        self.assertEqual(triple_stores[0]["username"], "test_user")
        self.assertEqual(triple_stores[0]["password"], "test_password")
        self.assertEqual(triple_stores[0]["gqe_uri"], Literal("http://example.com/gqe"))
        self.assertEqual(triple_stores[0]["input_graph"], Literal("http://example.com/input-graph"))

    def test_get_triple_stores_with_graphdb(self):
        triple_store_graph = Graph()
        rdf_type = URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")
        triple_store_type = TRIPLESTORE.GraphDb
        triple_store_uri = URIRef("https://mustrd.org/model/GraphDbConfig1")
        triple_store_graph.add((triple_store_uri, rdf_type, triple_store_type))
        triple_store_graph.add((triple_store_uri, TRIPLESTORE.url, Literal("http://graphdb.example.com:8080")))
        triple_store_graph.add((triple_store_uri, TRIPLESTORE.username, Literal("test_user")))
        triple_store_graph.add((triple_store_uri, TRIPLESTORE.password, Literal("test_password")))
        triple_store_graph.add((triple_store_uri, TRIPLESTORE.repository, Literal("Test")))
        triple_store_graph.add((triple_store_uri, TRIPLESTORE.inputGraph, Literal("http://example.com/input-graph")))

        triple_stores = get_triple_stores(triple_store_graph)

        self.assertEqual(len(triple_stores), 1)
        self.assertEqual(triple_stores[0]["type"], TRIPLESTORE.GraphDb)
        self.assertEqual(triple_stores[0]["url"], Literal("http://graphdb.example.com:8080"))
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
