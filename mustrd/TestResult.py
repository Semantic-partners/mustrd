from typing import Union
from itertools import groupby
from jinja2 import Environment, FileSystemLoader
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import os
import html
from mustrd.utils import get_mustrd_root


class testType(Enum):
    MUSTRD = "Mustrd"
    PYTEST = "Pytest"


class testStatus(Enum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


TEMPLATE_FOLDER = Path(os.path.join(get_mustrd_root(), "templates/"))


RESULT_LIST_MD_TEMPLATE = "md_ResultList_template.jinja"
RESULT_LIST_LEAF_MD_TEMPLATE = "md_ResultList_leaf_template.jinja"


@dataclass
class TestResult:
    test_name: str
    class_name: str
    module_name: str
    status: str
    is_mustrd: bool
    type: str
    given_files: list = None
    ontology_files: list = None
    shacl_files: list = None
    shacl_conforms: object = None
    ontology_conforms: object = None
    then_file: object = None
    shacl_report: object = None
    ontology_report: object = None
    failure_message: object = None

    def __init__(self, test_name: str, class_name: str, module_name: str, status: str, is_mustrd: bool,
                 given_files=None, ontology_files=None, shacl_files=None,
                 shacl_conforms=None, ontology_conforms=None, then_file=None,
                 shacl_report=None, ontology_report=None, failure_message=None):
        self.test_name = test_name
        self.class_name = class_name
        self.module_name = module_name
        self.status = status
        self.is_mustrd = is_mustrd
        self.type = testType.MUSTRD.value if self.is_mustrd else testType.PYTEST.value
        self.given_files = given_files or []
        self.ontology_files = ontology_files or []
        self.shacl_files = shacl_files or []
        self.shacl_conforms = shacl_conforms
        self.ontology_conforms = ontology_conforms
        self.then_file = then_file
        self.shacl_report = shacl_report
        self.ontology_report = ontology_report
        self.failure_message = failure_message


@dataclass
class Stats:
    count: int
    success_count: int
    fail_count: int
    skipped_count: int

    def __init__(self, count: int, success_count: int, fail_count: int, skipped_count: int):
        self.count = count
        self.success_count = success_count
        self.fail_count = fail_count
        self.skipped_count = skipped_count


def get_result_list(test_results: list[TestResult], *group_functions):
    if len(group_functions) > 0:
        return list(map(lambda key_group:
                        ResultList(key_group[0],
                                   get_result_list(key_group[1],
                                   *group_functions[1:]),
                                   len(group_functions) == 1),
                        groupby(sorted(test_results, key=group_functions[0]), group_functions[0])))
    else:
        return list(test_results)


@dataclass
class ResultList:
    name: str
    stats: Stats
    is_leaf: bool
    # string type to workaround recursive call
    result_list: Union[list['ResultList'], list[TestResult]]

    def __init__(self, name: str, result_list: Union[list['ResultList'], list[TestResult]], is_leaf: bool = False):
        self.name = name
        self.result_list = result_list
        self.is_leaf = is_leaf
        self.compute_stats()

    def compute_stats(self):
        count, success_count, fail_count, skipped_count = 0, 0, 0, 0

        if self.is_leaf:
            count = len(self.result_list)
            success_count = len(
                list(filter(lambda x: x.status == testStatus.PASSED.value, self.result_list)))
            fail_count = len(
                list(filter(lambda x: x.status == testStatus.FAILED.value, self.result_list)))
            skipped_count = len(
                list(filter(lambda x: x.status == testStatus.SKIPPED.value, self.result_list)))
        else:
            for test_results in self.result_list:
                sub_count, sub_success_count, sub_fail_count, sub_skipped_count = test_results.compute_stats()
                count += sub_count
                success_count += sub_success_count
                fail_count += sub_fail_count
                skipped_count += sub_skipped_count

        self.stats = Stats(count, success_count, fail_count, skipped_count)
        return count, success_count, fail_count, skipped_count

    def render(self):
        environment = Environment(loader=FileSystemLoader(TEMPLATE_FOLDER))

        def read_file(path):
            try:
                return html.escape(Path(path).read_text(encoding="utf-8"))
            except Exception as e:
                return html.escape(f"(could not read file: {e})")

        def escape_html(text):
            return html.escape(text) if text else text

        environment.globals['read_file'] = read_file
        environment.filters['escape_pipes'] = escape_html
        environment.filters['escape_html'] = escape_html
        template = RESULT_LIST_LEAF_MD_TEMPLATE if self.is_leaf else RESULT_LIST_MD_TEMPLATE
        rendered = environment.get_template(template).render(result_list=self.result_list, environment=environment)
        # CommonMark exits an HTML block on any blank line, breaking the layout.
        # Remove blank lines so the renderer stays in HTML mode throughout.
        return '\n'.join(line for line in rendered.splitlines() if line.strip())
