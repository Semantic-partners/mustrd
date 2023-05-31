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
import logger_setup
import sys
from rdflib import Graph
from mustrd import run_specs, get_triple_stores, review_results, get_specs
from pathlib import Path
from namespace import MUST

log = logger_setup.setup_logger(__name__)

def parse_args(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--put", help="Path under test - required", required=True)
    parser.add_argument("-v", "--verbose", help="verbose logging", action='store_true')
    parser.add_argument("-c", "--config", help="Path to triple store configuration", default=None)
    parser.add_argument("-g", "--given", help="Folder for given files", default=None)
    parser.add_argument("-w", "--when", help="Folder for when files", default=None)
    parser.add_argument("-t", "--then", help="Folder for then files", default=None)

    return parser.parse_args()

# https://github.com/Semantic-partners/mustrd/issues/108
def main(argv):

    args=parse_args(argv)
    path_under_test = Path(args.put)
    log.info(f"Path under test is {path_under_test}")

    if args.verbose:
        verbose = args.verbose
        log.info(f"Verbose set")

    if args.config is None:
        log.info(f"No triple store configuration added, running default configuration")
        triple_stores = [{'type': MUST.RdfLib}]
    else:
        triplestore_spec_path = Path(args.config)
        log.info(f"Path for triple store configuration is {triplestore_spec_path}")
        triple_stores = get_triple_stores(Graph().parse(triplestore_spec_path))

    if args.given is not None:
        given_path = Path(args.given)
        log.info(f"Path for given folder is {given_path}")
    if args.when is not None:
        when_path = Path(args.when)
        log.info(f"Path for when folder is {when_path}")
    if args.then is not None:
        then_path = Path(args.then)
        log.info(f"Path for then folder is {then_path}")

    spec_uris, spec_graph, results = get_specs(path_under_test, triple_stores)

    final_results = run_specs( spec_uris, spec_graph, results, triple_stores, given_path, when_path, then_path)

    review_results(final_results, verbose)

if __name__ == "__main__":
    main(sys.argv[1:])
