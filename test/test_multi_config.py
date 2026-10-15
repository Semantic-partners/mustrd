"""Several config files in one run: listed, globbed, or found by directory.

A suite split into one directory per domain, each with its own config, runs as a
whole from the CLI and from pytest. The fixture is laid out as

    ontology/<domain>/tests/mustrdconfig.ttl
    ontology/<domain>/specs/<domain>.mustrd.ttl
    ontology/shared/simple.ttl
"""
import subprocess
import sys
from pathlib import Path

import pytest

from mustrd.cli import main
from mustrd.config import check_pytest_paths_unique, find_config_files

CONFIG = """@prefix : <https://mustrd.org/mustrdTest/> .
@prefix triplestore: <https://mustrd.org/triplestore/> .

:{name} a :MustrdTest ;
    :hasSpecPath "../specs" ;
    :hasDataPath "../../shared" ;
    :hasPytestPath "{pytest_path}" ;
    :filterOnTripleStore triplestore:RdfLib .
"""

SPEC = """@prefix must: <https://mustrd.org/model/> .
@prefix ex:   <https://example.org/> .

ex:{name} a must:TestSpec ;
    must:given [ a must:FileDataset ; must:file "simple.ttl" ] ;
    must:when  [ a must:TextSparqlSource ;
                 must:queryText "PREFIX ex: <https://example.org/> SELECT ?v WHERE {{ ?s ex:value ?v }}" ;
                 must:queryType must:SelectSparql ] ;
    must:then  [ a must:TableDataset ;
                 must:hasRow [ must:hasBinding [ must:variable "v" ;
                                                 must:boundValue "one" ] ] ] .
"""

DATA = """@prefix ex: <https://example.org/> .
ex:s1 ex:value "one" .
"""


def domain(root: Path, name: str, pytest_path: str = None) -> Path:
    d = root / "ontology" / name
    (d / "specs").mkdir(parents=True)
    (d / "tests").mkdir()
    (d / "tests" / "mustrdconfig.ttl").write_text(
        CONFIG.format(name=name, pytest_path=pytest_path or name))
    (d / "specs" / f"{name}.mustrd.ttl").write_text(SPEC.format(name=name))
    return d / "tests" / "mustrdconfig.ttl"


@pytest.fixture
def suite(tmp_path):
    (tmp_path / "ontology" / "shared").mkdir(parents=True)
    (tmp_path / "ontology" / "shared" / "simple.ttl").write_text(DATA)
    configs = [domain(tmp_path, "finance"), domain(tmp_path, "claims")]
    return tmp_path, configs


GLOB = "ontology/*/tests/mustrdconfig.ttl"


def test_a_directory_finds_each_domain_config(suite):
    root, configs = suite
    # Data and spec files sit in the same tree and are not configs.
    assert sorted(find_config_files([root])) == sorted(configs)


def test_files_and_directories_mix_without_duplicates(suite):
    root, configs = suite
    found = find_config_files([configs[0], root])
    assert sorted(found) == sorted(configs)


def test_a_directory_with_no_config_is_an_error(tmp_path):
    with pytest.raises(ValueError, match="No mustrdTest:MustrdTest config"):
        find_config_files([tmp_path])


def test_a_glob_finds_each_domain_config(suite, monkeypatch):
    root, configs = suite
    monkeypatch.chdir(root)
    assert sorted(p.resolve() for p in find_config_files([GLOB])) == sorted(configs)
    assert len(find_config_files(["**/mustrdconfig.ttl"])) == 2


def test_a_glob_that_matches_nothing_is_an_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError, match="No config file matches"):
        find_config_files(["ontology/*/tests/mustrdconfig.ttl"])


def test_a_missing_path_is_an_error(tmp_path):
    with pytest.raises(ValueError, match="No such config"):
        find_config_files([tmp_path / "nope.ttl"])


def test_two_files_sharing_a_pytest_path_is_an_error(suite):
    root, configs = suite
    clash = domain(root, "policy", pytest_path="finance")
    with pytest.raises(ValueError, match="'finance'"):
        check_pytest_paths_unique(configs + [clash])


def test_cli_runs_every_domain(suite, capsys):
    root, _ = suite
    assert main(["report", "--config", str(root)]) == 0
    assert "2 passed, 0 not passed (2 specs)" in capsys.readouterr().out


def test_cli_takes_config_more_than_once(suite, capsys):
    _, configs = suite
    args = ["report"] + [a for c in configs for a in ("--config", str(c))]
    assert main(args) == 0
    assert "2 passed" in capsys.readouterr().out


def test_cli_takes_a_list_after_one_flag(suite, capsys):
    # What the shell hands over for --config ontology/*/tests/mustrdconfig.ttl
    _, configs = suite
    assert main(["report", "--config", *map(str, configs)]) == 0
    assert "2 passed" in capsys.readouterr().out


def test_cli_expands_a_quoted_glob(suite, capsys, monkeypatch):
    root, _ = suite
    monkeypatch.chdir(root)
    assert main(["report", "--config", GLOB]) == 0
    assert "2 passed" in capsys.readouterr().out


def test_cli_reports_a_pytest_path_clash(suite):
    root, _ = suite
    domain(root, "policy", pytest_path="finance")
    with pytest.raises(SystemExit, match="(?s)mustrd: .*'finance'"):
        main(["report", "--config", str(root)])


def pytest_in(root: Path, *args):
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "--mustrd", *args],
        cwd=root, capture_output=True, text=True)


def test_pytest_runs_every_domain_from_a_directory(suite):
    root, _ = suite
    result = pytest_in(root, "--config", ".")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "2 passed" in result.stdout


def test_pytest_takes_config_more_than_once(suite):
    root, _ = suite
    result = pytest_in(root, "--config", "ontology/finance/tests/mustrdconfig.ttl",
                       "--config", "ontology/claims/tests/mustrdconfig.ttl",
                       "--collect-only", "-q")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "finance.mustrd.ttl" in result.stdout
    assert "claims.mustrd.ttl" in result.stdout


def test_pytest_reports_a_pytest_path_clash(suite):
    root, _ = suite
    domain(root, "policy", pytest_path="finance")
    result = pytest_in(root, "--config", ".")
    assert result.returncode != 0
    assert "'finance'" in result.stderr


def test_pytest_takes_a_list_after_one_flag(suite):
    root, _ = suite
    result = pytest_in(root, "--config", "ontology/finance/tests/mustrdconfig.ttl",
                       "ontology/claims/tests/mustrdconfig.ttl")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "2 passed" in result.stdout


def test_pytest_takes_a_shell_glob(suite):
    root, _ = suite
    result = subprocess.run(
        f"{sys.executable} -m pytest -p no:cacheprovider --mustrd --config {GLOB}",
        shell=True, cwd=root, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "2 passed" in result.stdout


def test_pytest_expands_a_quoted_glob(suite):
    root, _ = suite
    result = pytest_in(root, "--config", GLOB)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "2 passed" in result.stdout


def test_pytest_keeps_test_paths_after_config_equals(suite):
    root, configs = suite
    result = pytest_in(root, f"--config={configs[0]}", "ontology/finance", "--collect-only", "-q")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "finance.mustrd.ttl" in result.stdout
    assert "claims.mustrd.ttl" not in result.stdout
