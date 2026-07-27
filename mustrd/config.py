"""The MustrdTest configuration file: parse it, SHACL-validate it, resolve paths.

A plain library with no pytest dependency, so the `mustrd` CLI (via runner.py) and
the pytest plugin read the same configuration the same way. It was extracted from
mustrdTestPlugin.py, which re-exports `TestConfig`/`parse_config` for callers that
still import them from there.
"""
import os
from dataclasses import dataclass
from pathlib import Path

from pyshacl import validate
from rdflib import Graph, RDF

from mustrd.namespace import MUSTRDTEST
from mustrd.utils import get_mustrd_root

mustrd_root = get_mustrd_root()


@dataclass(frozen=True)
class TestConfig:
    spec_path: Path
    data_path: Path
    triplestore_spec_path: Path
    pytest_path: str
    filter_on_tripleStore: str = None
    ontology_paths: tuple = ()


def get_config_param(config_graph, config_subject, config_param, convert_function):
    raw_value = config_graph.value(
        subject=config_subject, predicate=config_param, any=True
    )
    return convert_function(raw_value) if raw_value else None


def parse_config(config_path):
    """Every mustrdTest:MustrdTest in the config file, as TestConfigs.

    Paths are resolved relative to the config file, not the working directory, so
    a config can be run from anywhere. Raises ValueError if the file does not
    conform to mustrdTestShapes.ttl.
    """
    test_configs = []
    config_graph = Graph().parse(config_path)
    shacl_graph = Graph().parse(
        Path(os.path.join(mustrd_root, "model/mustrdTestShapes.ttl"))
    )
    ont_graph = Graph().parse(
        Path(os.path.join(mustrd_root, "model/mustrdTestOntology.ttl"))
    )
    conforms, results_graph, results_text = validate(
        data_graph=config_graph,
        shacl_graph=shacl_graph,
        ont_graph=ont_graph,
        advanced=True,
        inference="none",
    )
    if not conforms:
        raise ValueError(
            f"Mustrd test configuration not conform to the shapes. SHACL report: {results_text}",
            results_graph,
        )

    for test_config_subject in config_graph.subjects(
        predicate=RDF.type, object=MUSTRDTEST.MustrdTest
    ):
        spec_path = get_config_param(
            config_graph, test_config_subject, MUSTRDTEST.hasSpecPath, str
        )
        data_path = get_config_param(
            config_graph, test_config_subject, MUSTRDTEST.hasDataPath, str
        )
        triplestore_spec_path = get_config_param(
            config_graph, test_config_subject, MUSTRDTEST.triplestoreSpecPath, str
        )
        pytest_path = get_config_param(
            config_graph, test_config_subject, MUSTRDTEST.hasPytestPath, str
        )
        filter_on_tripleStore = tuple(
            config_graph.objects(
                subject=test_config_subject, predicate=MUSTRDTEST.filterOnTripleStore
            )
        )

        # Root path is the mustrd test config path
        root_path = Path(config_path).parent
        spec_path = root_path / Path(spec_path) if spec_path else None
        data_path = root_path / Path(data_path) if data_path else None
        triplestore_spec_path = (
            root_path / Path(triplestore_spec_path) if triplestore_spec_path else None
        )

        # hasOntologyPath may be repeated; each value is a file or a directory
        # (scanned recursively), resolved relative to the config file.
        ontology_paths = tuple(
            root_path / Path(str(o))
            for o in config_graph.objects(
                subject=test_config_subject, predicate=MUSTRDTEST.hasOntologyPath
            )
        )

        test_configs.append(
            TestConfig(
                spec_path=spec_path,
                data_path=data_path,
                triplestore_spec_path=triplestore_spec_path,
                pytest_path=pytest_path,
                filter_on_tripleStore=filter_on_tripleStore,
                ontology_paths=ontology_paths,
            )
        )
    return test_configs
