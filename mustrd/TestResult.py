from typing import Union
from itertools import groupby
from jinja2 import Environment, FileSystemLoader
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import os
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
CQ_TABLE_MD_TEMPLATE = "md_cq_table_template.jinja"
TERM_COVERAGE_MD_TEMPLATE = "md_term_coverage_template.jinja"
ONTOLOGIES_MD_TEMPLATE = "md_ontologies_template.jinja"
DUPLICATE_CQS_MD_TEMPLATE = "md_duplicate_cqs_template.jinja"
PER_CQ_MD_TEMPLATE = "md_per_cq_template.jinja"
CQ_GAPS_MD_TEMPLATE = "md_cq_gaps_template.jinja"


@dataclass
class TestResult:
    test_name: str
    class_name: str
    module_name: str
    status: str
    is_mustrd: bool
    type: str
    competency_question: str = None
    test_link: str = None
    module_link: str = None
    coverage_status: str = None

    def __init__(self, test_name: str, class_name: str, module_name: str, status: str, is_mustrd: bool,
                 competency_question: str = None, test_link: str = None, module_link: str = None,
                 coverage_status: str = None):
        self.test_name = test_name
        self.class_name = class_name
        self.module_name = module_name
        self.status = status
        self.is_mustrd = is_mustrd
        self.type = testType.MUSTRD.value if self.is_mustrd else testType.PYTEST.value
        self.competency_question = competency_question
        self.test_link = test_link
        self.module_link = module_link
        self.coverage_status = coverage_status


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
        template = RESULT_LIST_LEAF_MD_TEMPLATE if self.is_leaf else RESULT_LIST_MD_TEMPLATE
        return environment.get_template(template).render(result_list=self.result_list, environment=environment)


def render_cq_table(test_results: list, group_totals: dict = None) -> str:
    # Group by (module, class) — rendered as a heading — so those columns drop
    # out of the table. Insertion order is preserved (session result order).
    group_totals = group_totals or {}
    groups = {}
    for r in test_results:
        key = (r.module_name, r.class_name)
        if key not in groups:
            groups[key] = {"module_name": r.module_name, "module_link": r.module_link,
                           "class_name": r.class_name, "results": []}
        groups[key]["results"].append(r)
    group_list = list(groups.values())
    # Per group: how many CQs are shown out of all tests in that group.
    for g in group_list:
        g["cq_count"] = len(g["results"])
        g["total_tests"] = group_totals.get(g["class_name"], g["cq_count"])
    # The Coverage Status column only appears when term coverage was computed.
    show_coverage = any(getattr(r, "coverage_status", None) is not None for r in test_results)
    environment = Environment(loader=FileSystemLoader(TEMPLATE_FOLDER))
    return environment.get_template(CQ_TABLE_MD_TEMPLATE).render(
        groups=group_list, show_coverage=show_coverage)


def render_term_coverage(coverage: dict) -> str:
    environment = Environment(loader=FileSystemLoader(TEMPLATE_FOLDER))
    return environment.get_template(TERM_COVERAGE_MD_TEMPLATE).render(coverage=coverage)


def render_ontologies(ontologies: list) -> str:
    environment = Environment(loader=FileSystemLoader(TEMPLATE_FOLDER))
    return environment.get_template(ONTOLOGIES_MD_TEMPLATE).render(ontologies=ontologies)


def render_duplicate_cqs(duplicate_cqs: list) -> str:
    environment = Environment(loader=FileSystemLoader(TEMPLATE_FOLDER))
    return environment.get_template(DUPLICATE_CQS_MD_TEMPLATE).render(duplicate_cqs=duplicate_cqs)


def render_per_cq(per_cq: list, unchecked: bool = False) -> str:
    environment = Environment(loader=FileSystemLoader(TEMPLATE_FOLDER))
    return environment.get_template(PER_CQ_MD_TEMPLATE).render(per_cq=per_cq, unchecked=unchecked)


def render_cq_gaps(cq_gaps: list) -> str:
    environment = Environment(loader=FileSystemLoader(TEMPLATE_FOLDER))
    return environment.get_template(CQ_GAPS_MD_TEMPLATE).render(cq_gaps=cq_gaps)
