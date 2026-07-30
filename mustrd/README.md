# Developer helper

## Try it out

Ensure you have python3 installed, before you begin.
To install the necessary dependencies, run the following command from the project root.

`poetry install`

Run the following command to execute the accompanying tests specifications.

`python3 src/run.py -v -p "test/test-specs" -g "test/data" -w "test/data" -t "test/data"`

You will see some warnings. Do not worry, some tests specifications are invalid and intentionally skipped.

For a brief explanation of the meaning of these options use the help option.

`python3 src/run.py --help`

## Run the tests

Run `pytest` from the project root.

## Additional Notes for Developers
Mustrd remains very much under development. It is anticipated that additional functionality and triplestore support will be added over time. The project uses [Poetry](https://python-poetry.org/docs/) to manage dependencies so it will be necessary to have this installed to contribute towards the project. The link contains instructions on how to install and use this.

`pyproject.toml` and `poetry.lock` are the only sources of dependency truth. There is no exported `requirements.txt` to keep in step — the wheel is built by `poetry build`, and CI installs with `poetry install`.

We also recommend pairing MustRD with the VS Code plugin [faubulous.mentor](https://marketplace.visualstudio.com/items?itemName=faubulous.mentor) to enhance your development experience and streamline working with SPARQL and RDF specifications.

