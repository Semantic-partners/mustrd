# Developer helper

## Try it out

Ensure you have python3 installed, before you begin.
To install the necessary dependencies, run the following command from the project root.

`pip3 install  -r requirements.txt`

Run the following command to execute the accompanying tests specifications.

`python3 src/run.py -v -p "test/test-specs" -g "test/data" -w "test/data" -t "test/data"`

You will see some warnings. Do not worry, some tests specifications are invalid and intentionally skipped.

For a brief explanation of the meaning of these options use the help option.

`python3 src/run.py --help`

## Run the tests

Run `pytest` from the project root.

## Additional Notes for Developers
Mustrd remains very much under development. It is anticipated that additional functionality and triplestore support will be added over time. The project uses [Poetry](https://python-poetry.org/docs/) to manage dependencies so it will be necessary to have this installed to contribute towards the project. The link contains instructions on how to install and use this.
As the project is actually built from the requirements.txt file at the project root, it is necessary to export dependencies from poetry to this file before committing and pushing changes to the repository, using the following command.

`poetry export -f requirements.txt --without-hashes > requirements.txt`

