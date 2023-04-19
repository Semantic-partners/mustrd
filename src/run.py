import logger_setup
import sys
import getopt
from mustrd import run_specs, SpecPassed, SelectSpecFailure, ConstructSpecFailure, UpdateSpecFailure, \
    SpecPassedWithWarning, TripleStoreConnectionError, SparqlExecutionError, SparqlParseFailure, \
    TestSkipped, SpecificationError
from pathlib import Path
from colorama import Fore, Style
from tabulate import tabulate
from collections import defaultdict
from functools import reduce

log = logger_setup.setup_logger(__name__)


def main(argv):
    path_under_test = None
    triplestore_spec_path = None
    verbose = False
    opts, args = getopt.getopt(argv, "hvp:s:", ["put="])
    for opt, arg in opts:
        if opt == '-h':
            print('run.py -p <path_under_test> -s <triple_store_configuration_path>')
            sys.exit()
        elif opt in ("-p", "--put"):
            path_under_test = arg
            log.info(f"Path under test is {path_under_test}")
        if opt in ("-v", "--verbose"):
            log.info(f"Verbose set")
            verbose = True
        if opt in ("-s", "--store"):
            triplestore_spec_path = arg
            log.info(f"Path for triple store configuration is {triplestore_spec_path}")
    if not path_under_test:
        sys.exit("path_under_test not set")
    if not triplestore_spec_path:
        log.info(f"No triple store configuration added, running default configuration")

    if triplestore_spec_path:
        results = run_specs(Path(path_under_test), Path(triplestore_spec_path))
    else:
        results = run_specs(Path(path_under_test))

    print("===== Result Overview =====")
    # Get a list of all unique spec uris and triple stores
    spec_uris = list(set(result.spec_uri for result in results))
    triple_stores = list(set(result.triple_store for result in results))

    status_dict= defaultdict(lambda: defaultdict(int))
    status_counts = defaultdict(lambda: defaultdict(int))
    colours = defaultdict(lambda: defaultdict(int))

    colours[SpecPassed.__name__]= Fore.GREEN
    colours[SpecPassedWithWarning.__name__] = Fore.YELLOW
    colours[TestSkipped.__name__] = Fore.YELLOW
    # Populate the status dictionary with the results
    for result in results:
        type_name = type(result).__name__
        status_counts[result.triple_store][type_name] += 1
        if type(result) not in [SpecPassed, SpecPassedWithWarning, TestSkipped]:
            status_counts[result.triple_store]['failed'] += 1
        status_dict[result.spec_uri][result.triple_store] = f"{colours.get(type_name, Fore.RED)}{type_name}{Style.RESET_ALL}"

    all_status = list(set(status for inner_dict in status_counts.values() for status in inner_dict.keys()))

    # Convert the status dictionary to a list of rows for tabulate
    table_rows = [[spec_uri] + [status_dict[spec_uri][triple_store] for triple_store in triple_stores] for spec_uri in spec_uris]
    status_rows = [[f"{colours.get(status, Fore.RED)}{status}{Style.RESET_ALL}"] +
                   [f"{colours.get(status, Fore.RED)}{status_counts[triple_store][status] }{Style.RESET_ALL}" 
                    for triple_store in triple_stores] for status in all_status]

    print(tabulate(table_rows, headers=['Spec Uris / triple stores'] + triple_stores, tablefmt="pretty"))
    print(tabulate(status_rows, headers=['Status / triple stores'] + triple_stores, tablefmt="pretty"))

    agg_status = reduce(lambda acc, inner_dict: {k: acc.get(k, 0) + inner_dict.get(k, 0) for k in set(acc) | set(inner_dict)}, map(lambda outer_dict: outer_dict[1], status_counts.items()))

    pass_count = agg_status.get(SpecPassed.__name__, 0)
    warning_count = agg_status.get(SpecPassedWithWarning.__name__, 0)
    fail_count = agg_status.get('failed', 0)
    skipped_count = agg_status.get(TestSkipped.__name__, 0)

    overview_colour = Fore.GREEN
    if fail_count:
        overview_colour = Fore.RED
    elif skipped_count:
        overview_colour = Fore.RED
    elif warning_count:
        overview_colour = Fore.YELLOW

    logger_setup.flush()
    print(f"{overview_colour}===== {fail_count} failures, {skipped_count} skipped, {Fore.GREEN}{pass_count} passed, "
          f"{overview_colour}{warning_count} passed with warnings =====")

    if verbose and (fail_count or warning_count or skipped_count):
        for res in results:
            if type(res) == SelectSpecFailure:
                print(f"{Fore.RED}Failed {res.spec_uri} {res.triple_store}")
                print(res.message)
                print(res.table_comparison.to_markdown())
            if type(res) == ConstructSpecFailure or type(res) == UpdateSpecFailure:
                print(f"{Fore.RED}Failed {res.spec_uri} {res.triple_store}")
            if type(res) == SpecPassedWithWarning:
                print(f"{Fore.YELLOW}Passed with warning {res.spec_uri} {res.triple_store}")
                print(res.warning)
            if type(res) == TripleStoreConnectionError or type(res) == SparqlExecutionError or \
                    type(res) == SparqlParseFailure or type(res) == SpecificationError:
                print(f"{Fore.RED}Failed {res.spec_uri} {res.triple_store}")
                print(res.exception)
            if type(res) == TestSkipped:
                print(f"{Fore.YELLOW}Skipped {res.spec_uri} {res.triple_store}")
                print(res.message)

if __name__ == "__main__":
    main(sys.argv[1:])
