"""US-10: engine.record validates an agent result, stores it and advances."""

import copy
import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "workflow"))

import agent_steps  # noqa: E402
import engine  # noqa: E402
import state as st  # noqa: E402

CTX = SimpleNamespace(now=lambda: "t")
QA = {"tests_added": ["tests/test_x.py"], "red_run": {"failed": ["test_x"], "reason_expected": True}, "left_out": []}
IMPL = {"files": {"src/x.py": 3}, "tests_run": {"passed": 2, "failed": []}, "tests_disputed": []}


def _h(outcome, entry=None):
    return lambda state, ctx: (outcome, dict(entry or {}), state)


def _at(node):
    s = st.new_state("t", "b", "l")
    s["unit"] = 1
    return engine.enter({**s, "node": "write_unit"}, node)


def test_us10_wrong_step_id_is_refused_and_state_unchanged():
    s = _at("qa_write")
    before = copy.deepcopy(s)
    out, errors = engine.record(s, "u1-write-9", QA, CTX, {})
    assert errors
    assert json.dumps(out, sort_keys=True) == json.dumps(before, sort_keys=True)


def test_us10_invalid_qa_result_is_refused_naming_the_field():
    s = _at("qa_write")
    before = copy.deepcopy(s)
    bad = {"red_run": QA["red_run"]}
    out, errors = engine.record(s, s["pending"]["step_id"], bad, CTX, {})
    assert any("tests_added" in e for e in errors)
    assert json.dumps(out, sort_keys=True) == json.dumps(before, sort_keys=True)


def test_us10_valid_qa_result_runs_on_to_the_implement_step():
    s = _at("qa_write")
    h = {"red_run": _h("expected"), "commit_tests": _h("done")}
    out, errors = engine.record(s, s["pending"]["step_id"], QA, CTX, h)
    assert errors == []
    assert out["node"] == "implement"
    assert out["pending"]["agent"] == "implementer"
    first = out["history"][0]
    assert (first["node"], first["result"], first["to"]) == ("qa_write", QA, "red_run")


def test_us10_implementer_result_with_empty_tests_disputed_is_accepted():
    s = _at("implement")
    out, errors = engine.record(
        s,
        s["pending"]["step_id"],
        IMPL,
        CTX,
        {"tests_review": _h("PASS"), "verify": _h("fast"), "commit_fix": _h("done"), "next_unit": _h("last")},
    )
    assert errors == []
    assert out["history"][0]["node"] == "implement"
    assert out["history"][0]["to"] == "tests_review"


def test_us10_implementer_result_with_non_list_tests_disputed_is_refused():
    s = _at("implement")
    out, errors = engine.record(s, s["pending"]["step_id"], {**IMPL, "tests_disputed": "x"}, CTX, {})
    assert any("tests_disputed" in e for e in errors)
    assert out["history"] == []


def test_us10_qa_fix_and_subtract_shapes_validate():
    assert agent_steps.validate_result("qa_fix", {"tests_changed": ["a"]}) == []
    assert agent_steps.validate_result("subtract", {"removed": "x", "files": {"a.py": 4}}) == []
    assert agent_steps.validate_result("qa_fix", {"tests_changed": "a"})
    assert agent_steps.validate_result("subtract", {"removed": "x"})
    assert agent_steps.validate_result("implementer", {**IMPL, "tests_disputed": "x"})
    for key in ("qa_fix", "subtract"):
        assert agent_steps.validate_result(key, agent_steps.EXAMPLES[key]) == []


def test_us10_fast_unit_runs_end_to_end_to_next_unit():
    h = {
        "red_run": _h("expected"),
        "commit_tests": _h("done"),
        "tests_review": _h("PASS"),
        "verify": _h("fast"),
        "commit_fix": _h("done"),
        "next_unit": _h("last"),
    }
    s = _at("qa_write")
    s, errors = engine.record(s, s["pending"]["step_id"], QA, CTX, h)
    assert errors == [] and s["node"] == "implement"
    s, errors = engine.record(s, s["pending"]["step_id"], IMPL, CTX, h)
    assert errors == []
    assert s["node"] == "subtract"
    assert s["stage"] == "finish"
    assert s["pending"]["step"] == "subtract"
    nodes = [e["node"] for e in s["history"]]
    assert nodes == [
        "qa_write",
        "red_run",
        "commit_tests",
        "implement",
        "tests_review",
        "verify",
        "commit_fix",
        "next_unit",
    ]
