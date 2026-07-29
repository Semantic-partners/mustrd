"""Entry point for `python -m mustrd`.

Equivalent to the `mustrd` console script. Useful where the generated
`mustrd.exe` launcher can't be executed — locked-down Windows machines where
AV/EDR or AppLocker blocks unsigned executables in a venv's Scripts directory.
"""
import sys

from mustrd.cli import main

if __name__ == "__main__":
    sys.exit(main())
