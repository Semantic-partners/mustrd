import sys
import getopt
from mustrd import run_specs
from pathlib import Path

def main(argv):

    path_under_test = None
    opts, args = getopt.getopt(argv, "hp:", ["put="])
    for opt, arg in opts:
        if opt == '-h':
            print('run.py -p <path_under_test>')
            sys.exit()
        elif opt in ("-p", "--put"):
            path_under_test = arg
    if not path_under_test:
        sys.exit("path_under_test not set")
    print('Path under test is ', path_under_test)

    results = run_specs(Path(path_under_test))
    for res in results:
        print(f"{res.spec_uri} : {type(res).__name__}")


if __name__ == "__main__":
    main(sys.argv[1:])