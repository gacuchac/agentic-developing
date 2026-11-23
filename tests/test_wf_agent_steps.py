"""Tests for agent_steps.py: SCHEMAS and validate_result (US-10).

Path format asserted: dict keys joined by dots ("red_run.reason_expected",
"files.a.py"), list elements as "name[i]" ("tests_added[1]").
Extra keys not in the schema are allowed.
"""

import copy

import pytest

import agent_steps
from agent_steps import SCHEMAS, validate_result

QA = {"tests_added": ["tests/test_a.py"], "red_run": {"failed": ["t1"], "reason_expected": True}}
IMPL = {"files": {"a.py": 3, "b.py": 10}, "tests_run": {"passed": 4, "failed": []}}


def bad(base, **over):
    d = copy.deepcopy(base)
    for k, v in over.items():
        d[k] = v
    return d


def without(base, key):
    d = copy.deepcopy(base)
    del d[key]
    return d


def test_us10_schemas_exact_value():
    assert SCHEMAS == {
        "qa": {"tests_added": [str], "red_run": {"failed": [str], "reason_expected": bool}},
        "implementer": {"files": {str: int}, "tests_run": {"passed": int, "failed": [str]}},
    }


def test_us10_valid_qa_has_no_errors():
    assert validate_result("qa", QA) == []


def test_us10_valid_implementer_has_no_errors():
    assert validate_result("implementer", IMPL) == []


def test_us10_empty_lists_and_files_are_valid():
    assert validate_result("qa", {"tests_added": [], "red_run": {"failed": [], "reason_expected": False}}) == []
    assert validate_result("implementer", {"files": {}, "tests_run": {"passed": 0, "failed": []}}) == []


def test_us10_extra_keys_are_allowed():
    assert validate_result("qa", {**QA, "notes": "x"}) == []
    d = copy.deepcopy(IMPL)
    d["tests_run"]["extra"] = 1
    d["more"] = [1]
    assert validate_result("implementer", d) == []


def test_us10_missing_red_run_names_it():
    errs = validate_result("qa", without(QA, "red_run"))
    assert len(errs) == 1 and "red_run" in errs[0]


def test_us10_missing_tests_added_names_it():
    errs = validate_result("qa", without(QA, "tests_added"))
    assert len(errs) == 1 and "tests_added" in errs[0]


def test_us10_missing_nested_key_names_full_path():
    d = copy.deepcopy(QA)
    del d["red_run"]["reason_expected"]
    errs = validate_result("qa", d)
    assert len(errs) == 1 and "red_run.reason_expected" in errs[0]


def test_us10_missing_implementer_keys_named():
    errs = validate_result("implementer", {})
    assert len(errs) == 2
    assert any("files" in e for e in errs) and any("tests_run" in e for e in errs)
    d = copy.deepcopy(IMPL)
    del d["tests_run"]["passed"]
    errs = validate_result("implementer", d)
    assert len(errs) == 1 and "tests_run.passed" in errs[0]


def test_us10_reason_expected_string_fails():
    d = copy.deepcopy(QA)
    d["red_run"]["reason_expected"] = "yes"
    errs = validate_result("qa", d)
    assert len(errs) == 1 and "red_run.reason_expected" in errs[0]


def test_us10_file_count_string_fails_naming_file():
    errs = validate_result("implementer", bad(IMPL, files={"a.py": "3"}))
    assert len(errs) == 1 and "files.a.py" in errs[0]


def test_us10_file_key_wrong_type_not_a_valid_result():
    # JSON keys are always str, but a non-str key in a dict is still refused.
    assert validate_result("implementer", bad(IMPL, files={1: 3})) != []


def test_us10_files_not_a_dict_fails():
    errs = validate_result("implementer", bad(IMPL, files=["a.py"]))
    assert errs and all("files" in e for e in errs)


def test_us10_tests_added_not_a_list_fails():
    errs = validate_result("qa", bad(QA, tests_added="a.py"))
    assert len(errs) == 1 and "tests_added" in errs[0]


def test_us10_red_run_not_a_dict_fails():
    errs = validate_result("qa", bad(QA, red_run=[]))
    assert len(errs) == 1 and "red_run" in errs[0]


def test_us10_list_element_of_wrong_type_names_index():
    errs = validate_result("qa", bad(QA, tests_added=["a", 3]))
    assert len(errs) == 1 and "tests_added[1]" in errs[0]
    assert "tests_added[0]" not in errs[0]


def test_us10_nested_list_element_wrong_type_names_path():
    d = copy.deepcopy(IMPL)
    d["tests_run"]["failed"] = ["ok", "ok", None]
    errs = validate_result("implementer", d)
    assert len(errs) == 1 and "tests_run.failed[2]" in errs[0]


def test_us10_bool_not_accepted_as_int():
    d = copy.deepcopy(IMPL)
    d["tests_run"]["passed"] = True
    errs = validate_result("implementer", d)
    assert len(errs) == 1 and "tests_run.passed" in errs[0]
    errs = validate_result("implementer", bad(IMPL, files={"a.py": False}))
    assert len(errs) == 1 and "files.a.py" in errs[0]


def test_us10_int_not_accepted_as_bool():
    for v in (1, 0):
        d = copy.deepcopy(QA)
        d["red_run"]["reason_expected"] = v
        errs = validate_result("qa", d)
        assert len(errs) == 1 and "red_run.reason_expected" in errs[0]


def test_us10_several_bad_fields_give_one_error_each():
    d = {"tests_added": ["a", 3], "red_run": {"failed": "x", "reason_expected": "yes"}}
    errs = validate_result("qa", d)
    assert len(errs) == 3
    for path in ("tests_added[1]", "red_run.failed", "red_run.reason_expected"):
        assert sum(path in e for e in errs) == 1


def test_us10_several_bad_files_each_named():
    errs = validate_result("implementer", bad(IMPL, files={"a.py": "1", "b.py": 2.5, "c.py": 4}))
    assert len(errs) == 2
    assert any("files.a.py" in e for e in errs) and any("files.b.py" in e for e in errs)


def test_us10_errors_are_strings():
    errs = validate_result("qa", {})
    assert len(errs) == 2 and all(isinstance(e, str) for e in errs)


@pytest.mark.parametrize("data", [None, [], [1, 2], "text", 5, True])
@pytest.mark.parametrize("agent", ["qa", "implementer"])
def test_us10_non_dict_data_gives_error_without_raising(agent, data):
    errs = validate_result(agent, data)
    assert isinstance(errs, list) and len(errs) >= 1


def test_us10_unknown_agent_names_it():
    errs = validate_result("planner", QA)
    assert len(errs) >= 1 and any("planner" in e for e in errs)


def test_us10_unknown_agent_with_bad_data_does_not_raise():
    assert validate_result("planner", None) != []


def test_us10_validate_does_not_mutate_input():
    d = copy.deepcopy(QA)
    validate_result("qa", d)
    assert d == QA
