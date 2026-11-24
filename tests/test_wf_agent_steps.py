"""Tests for agent_steps.py: SCHEMAS and validate_result (US-10).

Path format asserted: dict keys joined by dots ("red_run.reason_expected",
"files.a.py"), list elements as "name[i]" ("tests_added[1]").
Extra keys not in the schema are allowed.
"""

import copy

import agent_steps
import pytest
from agent_steps import SCHEMAS, validate_result

QA = {"tests_added": ["tests/test_a.py"], "red_run": {"failed": ["t1"], "reason_expected": True}}
IMPL = {"files": {"a.py": 3, "b.py": 10}, "tests_run": {"passed": 4, "failed": []}, "tests_disputed": []}


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
    assert {
        "qa": {"tests_added": [str], "red_run": {"failed": [str], "reason_expected": bool}},
        "qa_fix": {"tests_changed": [str]},
        "implementer": {"files": {str: int}, "tests_run": {"passed": int, "failed": [str]}, "tests_disputed": [str]},
        "subtract": {"removed": str, "files": {str: int}},
    } == SCHEMAS
    assert agent_steps.EXAMPLES == {
        "qa": {"tests_added": ["tests/test_x.py"], "red_run": {"failed": ["test_x"], "reason_expected": True}},
        "qa_fix": {"tests_changed": ["tests/test_x.py"]},
        "implementer": {"files": {"src/x.py": 12}, "tests_run": {"passed": 3, "failed": []}, "tests_disputed": []},
        "subtract": {"removed": "unused helper", "files": {"src/x.py": 4}},
    }


def test_us10_valid_qa_has_no_errors():
    assert validate_result("qa", QA) == []


def test_us10_valid_implementer_has_no_errors():
    assert validate_result("implementer", IMPL) == []


def test_us10_empty_lists_and_files_are_valid():
    assert validate_result("qa", {"tests_added": [], "red_run": {"failed": [], "reason_expected": False}}) == []
    assert (
        validate_result("implementer", {"files": {}, "tests_run": {"passed": 0, "failed": []}, "tests_disputed": []})
        == []
    )


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
    assert len(errs) == 3
    assert any("files" in e for e in errs) and any("tests_run" in e for e in errs)
    assert any("tests_disputed" in e for e in errs)
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


# ---- render_prompt (US-10) ----
# No-commit phrase the default prompt must contain (case-insensitive): "do not commit".

import json
import re
from pathlib import Path

RUN = Path("/tmp/runs/proj/task-x")
REPO = Path("/tmp/work/repo-y")
UNIT = "### 3. thing\nLine two of the unit.\nFiles: `a.py`"


def render(agent="qa", step="write", step_id="u3-qa-1", template=None, unit=UNIT):
    return agent_steps.render_prompt(agent, step, step_id, RUN, REPO, unit, template)


def result_block(text):
    m = re.search(r"```workflow-result\s*\n(.*?)\n```", text, re.S)
    assert m, "no fenced workflow-result block"
    return json.loads(m.group(1))


def test_us10_prompt_first_line_is_wf_step():
    assert render().splitlines()[0] == "wf-step: u3-qa-1"


def test_us10_prompt_first_line_follows_step_id():
    a = render(step_id="u3-qa-1").splitlines()[0]
    b = render(step_id="u4-impl-2").splitlines()[0]
    assert b == "wf-step: u4-impl-2" and a != b


@pytest.mark.parametrize("agent,step", [("qa", "write"), ("implementer", "green")])
def test_us10_prompt_has_agent_step_run_repo_and_unit(agent, step):
    out = render(agent, step)
    assert agent in out and step in out
    assert str(RUN) in out and str(REPO) in out
    assert UNIT in out


@pytest.mark.parametrize("agent,example", [("qa", QA), ("implementer", IMPL)])
def test_us10_prompt_result_block_matches_schema(agent, example):
    data = result_block(render(agent, "x"))
    assert validate_result(agent, data) == []


def test_us10_prompt_result_block_differs_per_agent():
    assert result_block(render("qa")) != result_block(render("implementer"))


@pytest.mark.parametrize("agent", ["qa", "implementer"])
def test_us10_prompt_says_do_not_commit(agent):
    assert "do not commit" in render(agent).lower()


def test_us10_template_fills_placeholders_and_adds_nothing():
    t = "S={step_id}|R={run}|P={repo}|U={unit}"
    assert render(template=t) == f"S=u3-qa-1|R={RUN}|P={REPO}|U={UNIT}"


def test_us10_template_replaces_default():
    out = render(template="only {step_id}")
    assert out == "only u3-qa-1"


def test_us10_template_fills_schema():
    out = render("qa", template="{schema}")
    assert out.strip() and "{schema}" not in out and "tests_added" in out
    out = render("implementer", template="{schema}")
    assert "tests_run" in out


def test_us10_template_without_placeholders_is_returned_as_is():
    assert render(template="plain text") == "plain text"


def test_us10_template_unknown_placeholder_raises_keyerror():
    with pytest.raises(KeyError):
        render(template="hello {nope}")


# ---- the result example follows the step (US-17) ----


def test_us17_result_keys_map_each_step_to_its_result_shape():
    assert agent_steps.RESULT_KEYS == {
        "write": "qa",
        "fix": "qa_fix",
        "code": "implementer",
        "subtract": "subtract",
    }


def test_us17_default_prompt_for_subtract_shows_subtract_shape():
    out = render("implementer", "subtract")
    assert '"removed"' in out and '"tests_disputed"' not in out


def test_us17_default_prompt_for_fix_shows_qa_fix_shape():
    assert '"tests_changed"' in render("qa", "fix")


def test_us17_template_schema_for_subtract_is_the_subtract_example():
    out = render("implementer", "subtract", template="{schema}")
    assert json.loads(out) == agent_steps.EXAMPLES["subtract"]
