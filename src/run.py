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
from mustrd import run_specs, SpecPassed, SelectSpecFailure, ConstructSpecFailure, UpdateSpecFailure, \
    SpecPassedWithWarning, TripleStoreConnectionError, SparqlExecutionError, SparqlParseFailure, \
    SpecSkipped
from pathlib import Path
from colorama import Fore, Style
from tabulate import tabulate
from collections import defaultdict

log = logger_setup.setup_logger(__name__)


def main(argv):
    triplestore_spec_path = None
    given_path = None
    when_path = None
    then_path = None
    verbose = None

    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--put", help="Path under test - required", required=True)
    parser.add_argument("-v", "--verbose", help="verbose logging", action='store_true')
    parser.add_argument("-c", "--config", help="Path to triple store configuration", default=None)
    parser.add_argument("-g", "--given", help="Folder for given files", default=None)
    parser.add_argument("-w", "--when", help="Folder for when files", default=None)
    parser.add_argument("-t", "--then", help="Folder for then files", default=None)

    args = parser.parse_args()

    path_under_test = Path(args.put)
    log.info(f"Path under test is {path_under_test}")

    if args.verbose is not None:
        verbose = args.verbose
        log.info(f"Verbose set")

    if args.config is not None:
        triplestore_spec_path = args.config

    if args.given is not None:
        given_path = Path(args.given)
        log.info(f"Path for given folder is {given_path}")
    if args.when is not None:
        when_path = Path(args.when)
        log.info(f"Path for when folder is {when_path}")
    if args.then is not None:
        then_path = Path(args.then)
        log.info(f"Path for then folder is {then_path}")

    if triplestore_spec_path:
        log.info(f"Path for triple store configuration is {triplestore_spec_path}")
    else:
        log.info(f"No triple store configuration added, running default configuration")

    results = run_specs(path_under_test, triplestore_spec_path, given_path, when_path, then_path)

    print("===== Result Overview =====")
    # Init dictionaries
    status_dict = defaultdict(lambda: defaultdict(int))
    status_counts = defaultdict(lambda: defaultdict(int))
    colours = {SpecPassed: Fore.GREEN, SpecPassedWithWarning: Fore.YELLOW, SpecSkipped: Fore.YELLOW}
    # Populate dictionaries from results
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
    skipped_count = statuses.count(SpecSkipped)
    fail_count = len(list(filter(lambda status: status not in [SpecPassed, SpecPassedWithWarning, SpecSkipped], statuses)))

    if fail_count or skipped_count:
        overview_colour = Fore.RED
    elif warning_count:
        overview_colour = Fore.YELLOW
    else:
        overview_colour = Fore.GREEN

    logger_setup.flush()
    print(f"{overview_colour}===== {fail_count} failures, {Fore.YELLOW}{skipped_count} skipped, {Fore.GREEN}{pass_count} passed, "
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
                    type(res) == SparqlParseFailure:
                print(f"{Fore.RED}Failed {res.spec_uri} {res.triple_store}")
                print(res.exception)
            if type(res) == SpecSkipped:
                print(f"{Fore.YELLOW}Skipped {res.spec_uri} {res.triple_store}")
                print(res.message)


if __name__ == "__main__":
    main(sys.argv[1:])
