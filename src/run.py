import logger_setup
import sys
import getopt
from mustrd import run_specs, SpecPassed, SelectSpecFailure, ConstructSpecFailure, UpdateSpecFailure, \
    SpecPassedWithWarning, TripleStoreConnectionError, SparqlExecutionError, SparqlParseFailure, \
    SpecSkipped
from pathlib import Path
from colorama import Fore, Style

log = logger_setup.setup_logger(__name__)


def main(argv):
    path_under_test = None
    triplestore_spec_path = None
    given_path = None
    when_path = None
    then_path = None
    verbose = False
    opts, args = getopt.getopt(argv, "hvp:c:g:w:t:", ["put=", "given=", "when=", "then="])
    for opt, arg in opts:
        if opt == '-h':
            print('run.py -p <path_under_test> -c <triple_store_configuration_path> '
                  '-g <given_path> -w <when_path> -t <then_path>')
            sys.exit()
        elif opt in ("-p", "--put"):
            path_under_test = Path(arg)
            log.info(f"Path under test is {path_under_test}")
        if opt in ("-v", "--verbose"):
            log.info(f"Verbose set")
            verbose = True
        if opt in ("-c", "--config"):
            triplestore_spec_path = Path(arg)
            log.info(f"Path for triple store configuration is {triplestore_spec_path}")
        if opt in ("-g", "--given"):
            given_path = Path(arg)
            log.info(f"Path for given folder is {given_path}")
        if opt in ("-w", "--when"):
            when_path = Path(arg)
            log.info(f"Path for when folder is {when_path}")
        if opt in ("-t", "--then"):
            then_path = Path(arg)
            log.info(f"Path for then folder is {then_path}")
    if not path_under_test:
        sys.exit("path_under_test not set")
    if not triplestore_spec_path:
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
        elif type(res) == SpecSkipped:
            colour = Fore.YELLOW
            skipped_count += 1
        else:
            colour = Fore.RED
            fail_count += 1
        print(f"{res.spec_uri} {res.triple_store} {colour}{type(res).__name__}{Style.RESET_ALL}")

    overview_colour = Fore.GREEN
    if fail_count:
        overview_colour = Fore.RED
    elif skipped_count:
        overview_colour = Fore.YELLOW
    elif warning_count:
        overview_colour = Fore.YELLOW

    logger_setup.flush()
    print(f"{overview_colour}===== {Fore.RED}{fail_count} failures, {Fore.YELLOW}{skipped_count} skipped, {Fore.GREEN}{pass_count} passed, "
          f"{Fore.YELLOW}{warning_count} passed with warnings{overview_colour} =====")

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
