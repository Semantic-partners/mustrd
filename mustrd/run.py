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

import argparse
from . import logger_setup
import sys
import os
from rdflib import Graph
from .mustrd import get_triple_store_graph, run_specs, get_triple_stores, review_results, validate_specs, get_specs
from pathlib import Path
from .namespace import TRIPLESTORE
from .utils import get_mustrd_root
log = logger_setup.setup_logger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--put", help="Path under test - required", required=True)
    parser.add_argument("-v", "--verbose", help="verbose logging", action='store_true')
    parser.add_argument("-c", "--config", help="Path to triple store configuration", default=None)
    parser.add_argument("-d", "--data", help="Path to test data", default=None)
    parser.add_argument("-g", "--given", help="Override path for given files", default=None)
    parser.add_argument("-w", "--when", help="Override path for when files", default=None)
    parser.add_argument("-t", "--then", help="Override path for then files", default=None)
    parser.add_argument("--validate-only", help="Only validate specs, don't run them", action='store_true')

    return parser.parse_args()


# https://github.com/Semantic-partners/mustrd/issues/108
def main(argv):
    # Given_path = when_path = then_path = None
    project_root = get_mustrd_root()
    run_config = {}
    args = parse_args()
    run_config["spec_path"] = Path(args.put)
    log.info(f"Path under test is { run_config['spec_path']}")

    verbose = args.verbose
    if verbose:
        log.info("Verbose set")
        run_config["verbose"] = True

    if args.config:
        triplestore_spec_path = Path(args.config)
        log.info(f"Path for triple store configuration is {triplestore_spec_path}")
        triple_stores = get_triple_stores(get_triple_store_graph(triplestore_spec_path))
    else:
        log.info("No triple store configuration added, running default configuration")
        triple_stores = [{'type': TRIPLESTORE.RdfLib}]
    log.info("Triple Stores: " + str(triple_stores))
    if args.data:
        run_config["data_path"] = Path(args.data)
    else:
        run_config["data_path"] = Path(args.put)
    log.info(f"Path for test data folder is {run_config['data_path']}")

    if args.given:
        run_config["given_path"] = Path(args.given)
        log.info(f"Path for given folder is {run_config['given_path']}")

    if args.when:
        run_config["when_path"] = Path(args.when)
        log.info(f"Path for when folder is {run_config['when_path']}")

    if args.then:
        run_config["then_path"] = Path(args.then)
        log.info(f"Path for then folder is {run_config['then_path']}")

    shacl_graph = Graph().parse(Path(os.path.join(project_root, "model/mustrdShapes.ttl")))
    ont_graph = Graph().parse(Path(os.path.join(project_root, "model/ontology.ttl")))

    valid_spec_uris, spec_graph, invalid_spec_results = \
        validate_specs(run_config, triple_stores, shacl_graph, ont_graph)

    specs, skipped_spec_results = \
        get_specs(valid_spec_uris, spec_graph, triple_stores, run_config)

    # Handle validate-only mode
    if args.validate_only:
        log.info("Running validation-only mode")
        
        # Import validate_test_spec directly
        from .mustrd import validate_test_spec
        
        validation_results = []
        
        for spec in specs:
            try:
                # Use the spec_graph from the spec if available, otherwise fall back to the main spec_graph
                graph_to_validate = getattr(spec, 'spec_graph', spec_graph)
                warnings, errors = validate_test_spec(graph_to_validate, spec.spec_uri)
                
                print(f"\n=== Validation Results for {spec.spec_uri} ===")
                
                if warnings:
                    print("WARNINGS:")
                    for warning in warnings:
                        print(f"  ⚠️  {warning}")
                
                if errors:
                    print("ERRORS:")
                    for error in errors:
                        print(f"  ❌ {error}")
                
                if not warnings and not errors:
                    print("  ✅ No validation issues found")
                    
            except Exception as e:
                print(f"  🔥 Validation failed: {e}")
        
        print(f"\n=== Summary ===")
        print(f"Validated {len(specs)} test specs")
        print("Use --verbose for more detailed logging")
        return
    
    results = invalid_spec_results + skipped_spec_results + run_specs(specs)

    review_results(results, verbose)


if __name__ == "__main__":
    main(sys.argv[1:])
