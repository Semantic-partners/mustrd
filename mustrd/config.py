"""The MustrdTest configuration file: parse it, SHACL-validate it, resolve paths.

A plain library with no pytest dependency, so the `mustrd` CLI (via runner.py) and
the pytest plugin read the same configuration the same way. It was extracted from
mustrdTestPlugin.py, which re-exports `TestConfig`/`parse_config` for callers that
still import them from there.
"""
import glob
import os
from collections import defaultdict
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


def has_glob(path) -> bool:
    return glob.has_magic(str(path))


def _declares_mustrd_test(path: Path) -> bool:
    # Cheap text check first, so a data directory full of large .ttl files is not
    # parsed only to be thrown away; the parse then confirms it.
    try:
        if "MustrdTest" not in path.read_text(encoding="utf-8", errors="ignore"):
            return False
        graph = Graph().parse(path)
    except Exception:
        return False
    return (None, RDF.type, MUSTRDTEST.MustrdTest) in graph


def find_config_files(paths) -> list:
    """The config files named by `paths`: config files, directories, or glob
    patterns (`**` included).

    A directory is searched recursively for .ttl files that declare a
    mustrdTest:MustrdTest, so a suite split into one directory per domain can be
    run as a whole. Spec files (*.mustrd.ttl) are never configs. A pattern is
    expanded here as well as by the shell, so it works quoted and in pytest.ini.
    Raises ValueError for a path that does not exist, a pattern that matches
    nothing, or a directory holding no config.
    """
    expanded = []
    for path in map(str, paths):
        if has_glob(path) and not Path(path).exists():
            matches = sorted(glob.glob(path, recursive=True))
            if not matches:
                raise ValueError(f"No config file matches {path}")
            expanded.extend(matches)
        else:
            expanded.append(path)
    found = []
    for path in map(Path, expanded):
        if path.is_file():
            found.append(path)
        elif path.is_dir():
            configs = [f for f in sorted(path.rglob("*.ttl"))
                       if not f.name.endswith(".mustrd.ttl") and _declares_mustrd_test(f)]
            if not configs:
                raise ValueError(f"No mustrdTest:MustrdTest config found under {path}")
            found.extend(configs)
        else:
            raise ValueError(f"No such config file or directory: {path}")
    unique = []
    seen = set()
    for f in found:
        if f.resolve() not in seen:
            seen.add(f.resolve())
            unique.append(f)
    return unique


def check_pytest_paths_unique(config_files):
    """Raise ValueError if two config files give a MustrdTest the same pytest path.

    Within one file a shared pytest path is tolerated, as it always has been.
    Across files it is a mistake: --pytest-path could not pick one domain out, and
    the test IDs would differ only by a fallback suffix.
    """
    files_by_path = defaultdict(set)
    for config_file in config_files:
        for test_config in parse_config(config_file):
            files_by_path[test_config.pytest_path].add(str(config_file))
    clashes = {p: sorted(f) for p, f in files_by_path.items() if len(f) > 1}
    if clashes:
        lines = [f"  {p!r}: {', '.join(f)}" for p, f in sorted(clashes.items(), key=str)]
        raise ValueError(
            "Each config file needs its own mustrdTest:hasPytestPath, but these "
            "are shared:\n" + "\n".join(lines))
