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
        triple_stores =get_triple_stores(Graph().parse(triplestore_spec_path))

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
