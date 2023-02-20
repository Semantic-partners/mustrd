import sys
import getopt
from mustrd import run_specs, SpecPassed, SelectSpecFailure, ConstructSpecFailure
from pathlib import Path
from colorama import Fore, Style


def main(argv):
    path_under_test = None
    verbose = False
    opts, args = getopt.getopt(argv, "hvp:", ["put="])
    for opt, arg in opts:
        if opt == '-h':
            print('run.py -p <path_under_test>')
            sys.exit()
        elif opt in ("-p", "--put"):
            path_under_test = arg
        if opt in ("-v", "--verbose"):
            print("Verbose set")
            verbose = True
    if not path_under_test:
        sys.exit("path_under_test not set")
    print('Path under test is', path_under_test)

    results = run_specs(Path(path_under_test))
    pass_count = 0
    fail_count = 0
    for res in results:
        if type(res) == SpecPassed:
            colour = Fore.GREEN
            pass_count += 1
        else:
            colour = Fore.RED
            fail_count += 1
        print(f"{res.spec_uri} {colour}{type(res).__name__}{Style.RESET_ALL}")

    overview_colour = Fore.GREEN
    if fail_count:
        overview_colour = Fore.RED
    print(f"{overview_colour}===== {fail_count} failures, {Fore.GREEN}{pass_count} passed{overview_colour} =====")

    if verbose and fail_count:
        for res in results:
            if type(res) == SelectSpecFailure:
                print(f"Failed {res.spec_uri}")
                print(res.message)
                print(res.table_comparison.to_markdown())
            if type(res) == ConstructSpecFailure:
                print(f"Failed {res.spec_uri}")


if __name__ == "__main__":
    main(sys.argv[1:])
