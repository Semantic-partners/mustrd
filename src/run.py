import argparse
import logger_setup
import sys
from mustrd import run_specs, SpecPassed, SelectSpecFailure, ConstructSpecFailure, UpdateSpecFailure, \
    SpecPassedWithWarning, TripleStoreConnectionError, SparqlExecutionError, SparqlParseFailure, \
    TestSkipped, SpecificationError
from pathlib import Path
from colorama import Fore, Style

log = logger_setup.setup_logger(__name__)


# https://github.com/Semantic-partners/mustrd/issues/108
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

    pass_count = 0
    warning_count = 0
    fail_count = 0
    skipped_count = 0
    print("===== Result Overview =====")
    for res in results:
        if type(res) == SpecPassed:
            colour = Fore.GREEN
            pass_count += 1
        elif type(res) == SpecPassedWithWarning:
            colour = Fore.YELLOW
            warning_count += 1
        elif type(res) == TestSkipped:
            colour = Fore.YELLOW
            skipped_count += 1
        else:
            colour = Fore.RED
            fail_count += 1
        print(f"{res.spec_uri} {res.triple_store} {colour}{type(res).__name__}{Style.RESET_ALL}")

    if fail_count or skipped_count :
        overview_colour = Fore.RED
    elif warning_count:
        overview_colour = Fore.YELLOW
    else:
        overview_colour = Fore.GREEN

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
