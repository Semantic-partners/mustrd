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

from typing import Dict
from .mustrdTestPlugin import MustrdTestPlugin, TestConfig
from .utils import get_project_root
from rdflib import RDF, Graph
from .namespace import MUST
from collections import defaultdict

project_root = get_project_root()


def pytest_addoption(parser):
    group = parser.getgroup("md summary")
    group.addoption(
        "--md",
        action="store",
        dest="mdpath",
        metavar="path",
        default=None,
        help="create md summary file at that path.",
    )
    group.addoption(
        "--config",
        action="store",
        dest="configpath",
        metavar="path",
        default=None,
        required=True,
        help="Ttl file containing the list of test to construct.",
    )
    return


def pytest_configure(config) -> None:

    # Read configuration file
    test_configs: Dict[str, TestConfig] = defaultdict(lambda: defaultdict(list))
    config_graph = Graph().parse(project_root / config.getoption("configpath"))
    for test_config_subject in config_graph.subjects(predicate=RDF.type, object=MUST.TestConfig):
        test_function = get_config_param(config_graph, test_config_subject, MUST.hasTestFunction, str)
        spec_path = get_config_param(config_graph, test_config_subject, MUST.hasSpecPath, str)
        data_path = get_config_param(config_graph, test_config_subject, MUST.hasDataPath, str)
        triplestore_spec_path = get_config_param(config_graph, test_config_subject, MUST.triplestoreSpecPath, str)
        filter_on_tripleStore = list(config_graph.objects(subject=test_config_subject,
                                                          predicate=MUST.filterOnTripleStore))

        test_configs[test_function] = TestConfig(test_function=test_function,
                                                 spec_path=spec_path, data_path=data_path,
                                                 triplestore_spec_path=triplestore_spec_path,
                                                 filter_on_tripleStore=filter_on_tripleStore)

    config.pluginmanager.register(MustrdTestPlugin(config.getoption("mdpath"), test_configs))


def get_config_param(config_graph, config_subject, config_param, convert_function):
    raw_value = config_graph.value(subject=config_subject, predicate=config_param, any=True)
    return convert_function(raw_value) if raw_value else None
