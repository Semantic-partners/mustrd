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
    # Init dictionaries
    status_dict= defaultdict(lambda: defaultdict(int))
    status_counts = defaultdict(lambda: defaultdict(int))
    colours = {SpecPassed: Fore.GREEN, SpecPassedWithWarning: Fore.YELLOW, TestSkipped: Fore.YELLOW}
    # Populate dictionaries from resutls
    for result in results:
        status_counts[result.triple_store][type(result)] += 1
        status_dict[result.spec_uri][result.triple_store] = type(result)

    # Get the list of statuses and list of unique triple stores
    statuses = list(status for inner_dict in status_dict.values() for status in inner_dict.values())
    triple_stores = list(set(status for inner_dict in status_dict.values() for status in inner_dict.keys()))

    # Convert dictionaries to list for tabulate
    table_rows = [[spec_uri] + [f"{colours.get(status_dict[spec_uri][triple_store], Fore.RED)}{status_dict[spec_uri][triple_store].__name__ }{Style.RESET_ALL}"
                                for triple_store in triple_stores] for spec_uri in set(status_dict.keys())]
    
    status_rows = [[f"{colours.get(status, Fore.RED)}{status.__name__}{Style.RESET_ALL}"] +
                   [f"{colours.get(status, Fore.RED)}{status_counts[triple_store][status] }{Style.RESET_ALL}" 
                    for triple_store in triple_stores] for status in set(statuses)]

    # Display tables with tabulate
    print(tabulate(table_rows, headers=['Spec Uris / triple stores'] + triple_stores, tablefmt="pretty"))
    print(tabulate(status_rows, headers=['Status / triple stores'] + triple_stores, tablefmt="pretty"))

    pass_count = statuses.count(SpecPassed)
    warning_count = statuses.count(SpecPassedWithWarning)
    skipped_count = statuses.count(TestSkipped)
    fail_count = len(list(filter(lambda status: status not in [SpecPassed, SpecPassedWithWarning, TestSkipped], statuses)))

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
