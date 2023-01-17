from pathlib import Path
from rdflib import URIRef
from rdflib.namespace import Namespace

from mustrd import run_specs, SpecPassed, SelectSpecFailure


TEST_DATA = Namespace("https://semanticpartners.com/data/test/")
test_spec_path = Path("C:/Users/aymer/git/mustrd/test/anzotest/")
results = run_specs(test_spec_path)
results.sort(key=lambda sr: sr.spec_uri)
for spec in results:
    if type(spec) == SelectSpecFailure:
        table_diff = spec.table_comparison.to_markdown()
        print(f"spec URI: {spec.spec_uri}, table diff:\n {table_diff}")
assert results == [
    SpecPassed(URIRef(TEST_DATA.anzo_construct)),
    SpecPassed(URIRef(TEST_DATA.anzo_select)),
    SpecPassed(URIRef(TEST_DATA.rdflib__scenario_construct)),
    SpecPassed(URIRef(TEST_DATA.rdflib__scenario_select)),
], f"TTL files in path: {list(test_spec_path.glob('*.ttl'))}"
