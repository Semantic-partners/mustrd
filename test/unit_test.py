import unittest

from rdflib import Graph, Literal, URIRef, RDF

from mustrd.mustrd import get_triple_stores
from mustrd.namespace import TRIPLESTORE


class TestGetTripleStores(unittest.TestCase):
    def test_get_triple_stores_with_rdflib(self):
        triple_store_graph = Graph()
        rdf_type = URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")
        triple_store_type = TRIPLESTORE.RdfLib
        triple_store_graph.add((URIRef("http://example.org/rdflib-store"), rdf_type, triple_store_type))

        triple_stores = get_triple_stores(triple_store_graph)

        self.assertEqual(len(triple_stores), 1)
        self.assertEqual(triple_stores[0]["type"], TRIPLESTORE.RdfLib)

    def test_get_triple_stores_with_anzo(self):
        # Config in the graph, credentials in the map — the way real runs load them.
        triple_store_uri = URIRef("https://mustrd.org/model/AnzoConfig1")
        triple_store_graph = Graph()
        triple_store_graph.add((triple_store_uri, RDF.type, TRIPLESTORE.Anzo))
        triple_store_graph.add((triple_store_uri, TRIPLESTORE.url, Literal("http://anzo.example.com:8080")))
        triple_store_graph.add((triple_store_uri, TRIPLESTORE.gqeURI, Literal("http://example.com/gqe")))
        triple_store_graph.add((triple_store_uri, TRIPLESTORE.inputGraph, Literal("http://example.com/input-graph")))
        triple_store_graph.add((triple_store_uri, TRIPLESTORE.outputGraph, Literal("http://example.com/output-graph")))
        credentials = {str(triple_store_uri): {"username": "test_user", "password": "test_password"}}

        triple_stores = get_triple_stores(triple_store_graph, credentials)

        self.assertEqual(len(triple_stores), 1)
        self.assertEqual(triple_stores[0]["type"], TRIPLESTORE.Anzo)
        self.assertEqual(triple_stores[0]["url"], Literal("http://anzo.example.com:8080"))
        self.assertEqual(triple_stores[0]["username"], "test_user")
        self.assertEqual(triple_stores[0]["password"], "test_password")
        self.assertEqual(triple_stores[0]["gqe_uri"], Literal("http://example.com/gqe"))
        self.assertEqual(triple_stores[0]["input_graph"], Literal("http://example.com/input-graph"))

    def test_get_triple_stores_with_graphdb(self):
        triple_store_uri = URIRef("https://mustrd.org/model/GraphDbConfig1")
        triple_store_graph = Graph()
        triple_store_graph.add((triple_store_uri, RDF.type, TRIPLESTORE.GraphDb))
        triple_store_graph.add((triple_store_uri, TRIPLESTORE.url, Literal("http://graphdb.example.com:8080")))
        triple_store_graph.add((triple_store_uri, TRIPLESTORE.repository, Literal("Test")))
        triple_store_graph.add((triple_store_uri, TRIPLESTORE.inputGraph, Literal("http://example.com/input-graph")))
        credentials = {str(triple_store_uri): {"username": "test_user", "password": "test_password"}}

        triple_stores = get_triple_stores(triple_store_graph, credentials)

        self.assertEqual(len(triple_stores), 1)
        self.assertEqual(triple_stores[0]["type"], TRIPLESTORE.GraphDb)
        self.assertEqual(triple_stores[0]["url"], Literal("http://graphdb.example.com:8080"))
        self.assertEqual(triple_stores[0]["username"], "test_user")
        self.assertEqual(triple_stores[0]["password"], "test_password")
        self.assertEqual(triple_stores[0]["repository"], Literal("Test"))
        self.assertEqual(triple_stores[0]["input_graph"], Literal("http://example.com/input-graph"))

    def test_get_triple_stores_reads_credentials_embedded_in_graph_as_fallback(self):
        # Back-compat: a direct caller that passes no credentials map still gets
        # auth read from the graph. Pins the fallback so it isn't lost.
        triple_store_uri = URIRef("https://mustrd.org/model/GraphDbConfig1")
        triple_store_graph = Graph()
        triple_store_graph.add((triple_store_uri, RDF.type, TRIPLESTORE.GraphDb))
        triple_store_graph.add((triple_store_uri, TRIPLESTORE.url, Literal("http://graphdb.example.com:8080")))
        triple_store_graph.add((triple_store_uri, TRIPLESTORE.repository, Literal("Test")))
        triple_store_graph.add((triple_store_uri, TRIPLESTORE.username, Literal("test_user")))
        triple_store_graph.add((triple_store_uri, TRIPLESTORE.password, Literal("test_password")))

        triple_stores = get_triple_stores(triple_store_graph)

        self.assertEqual(triple_stores[0]["username"], "test_user")
        self.assertEqual(triple_stores[0]["password"], "test_password")

    def test_get_triple_stores_with_stardog_token(self):
        triple_store_uri = URIRef("https://mustrd.org/model/StardogConfig1")
        triple_store_graph = Graph()
        triple_store_graph.add((triple_store_uri, RDF.type, TRIPLESTORE.Stardog))
        triple_store_graph.add((triple_store_uri, TRIPLESTORE.url, Literal("http://stardog.example.com")))
        triple_store_graph.add((triple_store_uri, TRIPLESTORE.port, Literal("5820")))
        triple_store_graph.add((triple_store_uri, TRIPLESTORE.database, Literal("mustrd")))
        triple_store_graph.add((triple_store_uri, TRIPLESTORE.inputGraph, Literal("http://example.com/input-graph")))
        triple_store_graph.add((triple_store_uri, TRIPLESTORE.materialisedGraph, Literal("http://example.com/materialised-1")))
        triple_store_graph.add((triple_store_uri, TRIPLESTORE.virtualGraph, Literal("virtual://source-a")))
        credentials = {str(triple_store_uri): {"token": "my-bearer-token"}}

        triple_stores = get_triple_stores(triple_store_graph, credentials)

        self.assertEqual(len(triple_stores), 1)
        ts = triple_stores[0]
        self.assertNotIn("error", ts)
        self.assertEqual(ts["type"], TRIPLESTORE.Stardog)
        self.assertEqual(ts["database"], Literal("mustrd"))
        self.assertEqual(ts["token"], "my-bearer-token")
        # No basic-auth credentials when a token is supplied
        self.assertIsNone(ts.get("username"))
        self.assertEqual(ts["input_graph"], Literal("http://example.com/input-graph"))
        self.assertEqual(ts["materialised_graphs"], ["http://example.com/materialised-1"])
        self.assertEqual(ts["virtual_graphs"], ["virtual://source-a"])

    def test_get_triple_stores_with_stardog_basic_auth_fallback(self):
        triple_store_uri = URIRef("https://mustrd.org/model/StardogConfig2")
        triple_store_graph = Graph()
        triple_store_graph.add((triple_store_uri, RDF.type, TRIPLESTORE.Stardog))
        triple_store_graph.add((triple_store_uri, TRIPLESTORE.url, Literal("http://stardog.example.com:5820")))
        triple_store_graph.add((triple_store_uri, TRIPLESTORE.database, Literal("mustrd")))
        triple_store_graph.add((triple_store_uri, TRIPLESTORE.inputGraph, Literal("http://example.com/input-graph")))
        credentials = {str(triple_store_uri): {"username": "admin", "password": "admin"}}

        triple_stores = get_triple_stores(triple_store_graph, credentials)

        self.assertEqual(len(triple_stores), 1)
        ts = triple_stores[0]
        self.assertNotIn("error", ts)
        self.assertIsNone(ts.get("token"))
        self.assertEqual(ts["username"], "admin")
        self.assertEqual(ts["password"], "admin")

    def test_get_triple_stores_stardog_requires_auth(self):
        # No credentials supplied for the store -> flagged as an error.
        triple_store_uri = URIRef("https://mustrd.org/model/StardogConfig3")
        triple_store_graph = Graph()
        triple_store_graph.add((triple_store_uri, RDF.type, TRIPLESTORE.Stardog))
        triple_store_graph.add((triple_store_uri, TRIPLESTORE.url, Literal("http://stardog.example.com:5820")))
        triple_store_graph.add((triple_store_uri, TRIPLESTORE.database, Literal("mustrd")))
        triple_store_graph.add((triple_store_uri, TRIPLESTORE.inputGraph, Literal("http://example.com/input-graph")))

        triple_stores = get_triple_stores(triple_store_graph, credentials={})

        self.assertEqual(len(triple_stores), 1)
        self.assertIn("error", triple_stores[0])

    def test_secrets_never_enter_config_graph(self):
        # The config graph is loaded on its own; secrets are parsed separately
        # into the map and must not appear in the config graph.
        import tempfile
        from pathlib import Path
        from mustrd.mustrd import get_triple_store_graph, get_credentials
        from mustrd.namespace import TRIPLESTORE

        with tempfile.TemporaryDirectory() as d:
            config_path = Path(d) / "ts.ttl"
            config_path.write_text(
                "@prefix : <https://mustrd.org/triplestore/> .\n"
                ":store a :GraphDb ; :url \"http://localhost\" ; :repository \"r\" .\n"
            )
            (Path(d) / "ts_secrets.ttl").write_text(
                "@prefix : <https://mustrd.org/triplestore/> .\n"
                ":store :username \"admin\" ; :password \"s3cret\" .\n"
            )

            config_graph = get_triple_store_graph(config_path)
            credentials = get_credentials(config_path)

            # No password/username triple leaked into the config graph
            self.assertEqual(list(config_graph.triples((None, TRIPLESTORE.password, None))), [])
            self.assertEqual(list(config_graph.triples((None, TRIPLESTORE.username, None))), [])
            serialised = config_graph.serialize(format="ttl")
            self.assertNotIn("s3cret", serialised)
            # ...but they are in the credentials map
            store = URIRef("https://mustrd.org/triplestore/store")
            self.assertEqual(credentials[str(store)], {"username": "admin", "password": "s3cret"})

    def _stardog_config(self, d, extra):
        from pathlib import Path
        path = Path(d) / "ts.ttl"
        path.write_text(
            "@prefix : <https://mustrd.org/triplestore/> .\n"
            ':store a :Stardog ; :url "http://localhost" ; :database "db" ;\n'
            f"    {extra} .\n"
        )
        return path

    STORE = "https://mustrd.org/triplestore/store"

    def test_token_from_env_var_pointer(self):
        import os
        import tempfile
        from unittest import mock
        from mustrd.mustrd import get_credentials, get_triple_store_graph

        with tempfile.TemporaryDirectory() as d:
            config = self._stardog_config(d, ':tokenEnv "MUSTRD_TEST_TOKEN"')
            with mock.patch.dict(os.environ, {"MUSTRD_TEST_TOKEN": " env-token \n"}):
                credentials = get_credentials(config)
            self.assertEqual(credentials[self.STORE], {"token": "env-token"})
            # The config graph holds the variable name, never the token.
            self.assertNotIn("env-token", get_triple_store_graph(config).serialize(format="ttl"))

    def test_token_from_file_pointer_relative_to_config(self):
        import tempfile
        from pathlib import Path
        from mustrd.mustrd import get_credentials

        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "sub").mkdir()
            (Path(d) / ".token").write_text("file-token\n")
            config = self._stardog_config(d, ':tokenFile "../.token"')
            config = config.rename(Path(d) / "sub" / "ts.ttl")
            self.assertEqual(get_credentials(config)[self.STORE], {"token": "file-token"})

    def test_pointer_beats_stale_secrets_file(self):
        import tempfile
        from pathlib import Path
        from mustrd.mustrd import get_credentials

        with tempfile.TemporaryDirectory() as d:
            (Path(d) / ".token").write_text("fresh")
            config = self._stardog_config(d, ':tokenFile ".token"')
            (Path(d) / "ts_secrets.ttl").write_text(
                '@prefix : <https://mustrd.org/triplestore/> .\n:store :token "stale" .\n'
            )
            self.assertEqual(get_credentials(config)[self.STORE], {"token": "fresh"})

    def test_unresolved_pointer_falls_back_to_secrets_file(self):
        import os
        import tempfile
        from pathlib import Path
        from unittest import mock
        from mustrd.mustrd import get_credentials

        with tempfile.TemporaryDirectory() as d:
            config = self._stardog_config(
                d, ':tokenEnv "MUSTRD_TEST_UNSET" ; :tokenFile "missing.token"'
            )
            (Path(d) / "ts_secrets.ttl").write_text(
                '@prefix : <https://mustrd.org/triplestore/> .\n:store :token "from-ci" .\n'
            )
            with mock.patch.dict(os.environ, {}, clear=False):
                os.environ.pop("MUSTRD_TEST_UNSET", None)
                credentials = get_credentials(config)
            self.assertEqual(credentials[self.STORE], {"token": "from-ci"})

    def test_env_pointer_tried_before_file_pointer(self):
        import os
        import tempfile
        from pathlib import Path
        from unittest import mock
        from mustrd.mustrd import get_credentials

        with tempfile.TemporaryDirectory() as d:
            (Path(d) / ".token").write_text("from-file")
            config = self._stardog_config(d, ':tokenEnv "MUSTRD_TEST_TOKEN" ; :tokenFile ".token"')
            with mock.patch.dict(os.environ, {"MUSTRD_TEST_TOKEN": "from-env"}):
                self.assertEqual(get_credentials(config)[self.STORE], {"token": "from-env"})

    def test_inline_secrets_win_over_pointers(self):
        import tempfile
        from pathlib import Path
        from mustrd.mustrd import get_credentials

        with tempfile.TemporaryDirectory() as d:
            (Path(d) / ".token").write_text("from-file")
            config = self._stardog_config(d, ':tokenFile ".token"')
            inline = '@prefix : <https://mustrd.org/triplestore/> .\n:store :token "inline" .\n'
            self.assertEqual(get_credentials(config, inline)[self.STORE], {"token": "inline"})

    def test_token_pointers_pass_the_stardog_shape(self):
        import tempfile
        from mustrd.mustrd import get_credentials, get_triple_store_graph, get_triple_stores

        with tempfile.TemporaryDirectory() as d:
            config = self._stardog_config(d, ':tokenEnv "X" ; :tokenFile ".token"')
            stores = get_triple_stores(get_triple_store_graph(config), get_credentials(config))
            self.assertEqual(len(stores), 1)

    def test_credentials_extracted_into_map_keyed_by_store(self):
        from mustrd.mustrd import extract_credentials
        g = Graph()
        a = URIRef("https://mustrd.org/model/A")
        b = URIRef("https://mustrd.org/model/B")
        g.add((a, TRIPLESTORE.username, Literal("user-a")))
        g.add((a, TRIPLESTORE.password, Literal("pass-a")))
        g.add((b, TRIPLESTORE.token, Literal("token-b")))

        credentials = extract_credentials(g)

        self.assertEqual(credentials[str(a)], {"username": "user-a", "password": "pass-a"})
        self.assertEqual(credentials[str(b)], {"token": "token-b"})

    def test_apply_credentials_only_sets_what_is_present(self):
        from mustrd.mustrd import apply_credentials
        a = URIRef("https://mustrd.org/model/A")
        credentials = {str(a): {"username": "user-a", "password": "pass-a"}}
        ts = {}
        apply_credentials(ts, a, credentials)
        self.assertEqual(ts, {"username": "user-a", "password": "pass-a"})

        # A store with no entry in the map gets nothing set — not the string "None".
        ts2 = {}
        apply_credentials(ts2, URIRef("https://mustrd.org/model/missing"), credentials)
        self.assertEqual(ts2, {})

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
