"""US-7: engine.enter sets the node, round and the pending step its kind requires."""

import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "workflow"))

import engine  # noqa: E402
import state as st  # noqa: E402


def _state(node="write_unit", unit=1):
    s = st.new_state("t", "b", "l")
    s["unit"], s["node"] = unit, node
    return s


def test_us7_enter_agent_after_a_back_round_numbers_the_step_id():
    s = _state("impl_decide", unit=3)
    for _ in range(2):
        s = st.with_entry(s, {"node": "implement", "result": {}, "to": "tests_review"}, "n")
    s = st.with_entry(s, {"node": "impl_decide", "decision": "correct", "to": "implement"}, "n")
    out = engine.enter(s, "implement")
    assert out["node"] == "implement"
    assert out["round"] == 2
    assert out["pending"] == {"kind": "agent", "agent": "implementer", "step": "code", "step_id": "u3-code-3"}


def test_us35_enter_agent_step_id_counts_attempts_at_the_node_in_this_unit_only():
    s = _state("commit_tests", unit=2)
    s = st.with_entry(s, {"node": "implement", "result": {}, "to": "tests_review"}, "n")
    s["unit"] = 1
    s = st.with_entry(s, {"node": "implement", "result": {}, "to": "tests_review"}, "n")
    s = st.with_entry(s, {"node": "commit_tests", "outcome": "done", "to": "implement"}, "n")
    out = engine.enter(s, "implement")
    assert out["round"] == 1
    assert out["pending"]["step_id"] == "u1-code-2"


def test_us7_enter_agent_first_time_is_round_one():
    out = engine.enter(_state(), "qa_write")
    assert out["round"] == 1
    assert out["pending"] == {"kind": "agent", "agent": "qa", "step": "write", "step_id": "u1-write-1"}


def test_us7_enter_ignores_back_rounds_of_other_units():
    s = _state("impl_decide", unit=2)
    s = st.with_entry(s, {"node": "impl_decide", "decision": "correct", "to": "implement"}, "n")
    s["unit"] = 3
    out = engine.enter(s, "implement")
    assert out["round"] == 1
    assert out["pending"]["step_id"] == "u3-code-1"


def test_us7_enter_user_from_impl_decide_lists_resume_nodes():
    out = engine.enter(_state("impl_decide"), "user", "stuck")
    p = out["pending"]
    assert p["kind"] == "user"
    assert p["from"] == "impl_decide"
    assert p["reason"] == "stuck"
    assert p["resume"] == ["commit_fix", "impl_decide", "implement"]


def test_us7_enter_user_from_commit_fix_can_resume_commit_fix():
    out = engine.enter(_state("commit_fix"), "user")
    assert out["pending"]["resume"] == ["commit_fix", "implement", "next_unit"]
    assert out["pending"]["reason"] == ""


def test_us7_enter_done_is_end():
    assert engine.enter(_state("answers_ask"), "done")["pending"] == {"kind": "end"}


def test_us7_enter_decide_node_is_decide():
    out = engine.enter(_state("impl_review"), "impl_decide")
    assert out["node"] == "impl_decide"
    assert out["pending"] == {"kind": "decide"}


def test_us7_enter_auto_node_is_auto():
    out = engine.enter(_state("implement"), "tests_review")
    assert out["node"] == "tests_review"
    assert out["pending"] == {"kind": "auto"}


def test_us7_enter_subtract_sets_stage_finish():
    out = engine.enter(_state("next_unit"), "subtract")
    assert out["stage"] == "finish"
    assert out["pending"]["step"] == "subtract"


def test_us7_enter_other_node_keeps_stage():
    assert engine.enter(_state("write_unit"), "qa_write")["stage"] == "build"


def test_us7_enter_does_not_mutate_the_input():
    s = st.with_entry(
        _state("impl_decide", unit=3), {"node": "impl_decide", "decision": "correct", "to": "implement"}, "n"
    )
    before = copy.deepcopy(s)
    out = engine.enter(s, "implement")
    assert json.dumps(s, sort_keys=True) == json.dumps(before, sort_keys=True)
    assert out is not s
