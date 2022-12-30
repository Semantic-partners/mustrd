from pathlib import Path

from rdflib import URIRef
from rdflib.namespace import Namespace

from mustrd import run_specs, SpecResult

TEST_DATA = Namespace("https://semanticpartners.com/data/test/")


class TestRunSpecs:
    def test_find_specs_in_path_and_run_them(self):
        test_spec_path = Path("test-specs/")

        results = run_specs(test_spec_path)
        results.sort(key=lambda sr: sr.spec_uri)
        assert results == [
            SpecResult(URIRef(TEST_DATA.a_complete_construct_scenario)),
            SpecResult(URIRef(TEST_DATA.a_complete_select_scenario))
        ], f"TTL files in path: {list(test_spec_path.glob('**/*.ttl'))}"
