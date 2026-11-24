"""US-7: engine.advance runs auto nodes through handlers and stops at the first non-auto node."""

import copy
import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "workflow"))

import engine  # noqa: E402
import state as st  # noqa: E402

CTX = SimpleNamespace(now=lambda: "t")


def _state(node="write_unit", unit=1):
    s = st.new_state("t", "b", "l")
    s["unit"], s["node"] = unit, node
    return s


def _h(outcome, entry=None):
    return lambda state, ctx: (outcome, dict(entry or {}), state)


def test_us7_advance_write_unit_stops_at_qa_write():
    out = engine.advance(_state("write_unit"), CTX, {"write_unit": _h("done")})
    assert out["node"] == "qa_write"
    assert len(out["history"]) == 1
    e = out["history"][0]
    assert (e["node"], e["outcome"], e["to"]) == ("write_unit", "done", "qa_write")
    assert out["pending"] == {"kind": "agent", "agent": "qa", "step": "write", "step_id": "u1-write-1"}


def test_us7_advance_refused_commit_fix_goes_to_implement_with_error():
    h = {"commit_fix": _h("refused", {"error": "hook said no"})}
    out = engine.advance(_state("commit_fix"), CTX, h)
    assert out["node"] == "implement"
    assert out["history"][-1]["error"] == "hook said no"
    assert out["history"][-1]["to"] == "implement"
    assert out["pending"]["kind"] == "agent"


def test_us7_advance_fourth_refused_commit_fix_goes_to_user():
    s = _state("commit_fix")
    for _ in range(3):
        s = st.with_entry(s, {"node": "commit_fix", "outcome": "refused", "to": "implement"}, "n")
    h = {"commit_fix": _h("refused", {"error": "hook said no"})}
    out = engine.advance(s, CTX, h)
    assert out["node"] == "user"
    assert out["pending"]["kind"] == "user"
    assert out["pending"]["from"] == "commit_fix"
    assert out["pending"]["reason"]
    assert out["history"][-1]["to"] == "user"


def test_us7_advance_third_refused_commit_fix_still_goes_to_implement():
    s = _state("commit_fix")
    for _ in range(2):
        s = st.with_entry(s, {"node": "commit_fix", "outcome": "refused", "to": "implement"}, "n")
    out = engine.advance(s, CTX, {"commit_fix": _h("refused", {"error": "x"})})
    assert out["node"] == "implement"
    assert out["pending"]["step_id"] == "u1-code-3"


def test_us7_advance_malformed_tests_review_goes_to_user():
    out = engine.advance(_state("tests_review"), CTX, {"tests_review": _h("MALFORMED")})
    assert out["node"] == "user"
    assert out["pending"]["kind"] == "user"
    assert out["history"][-1]["outcome"] == "MALFORMED"


def test_us7_advance_chains_auto_nodes_until_an_agent_node():
    h = {"red_run": _h("expected"), "commit_tests": _h("done", {"sha": "abc"})}
    out = engine.advance(_state("red_run"), CTX, h)
    assert [e["node"] for e in out["history"]] == ["red_run", "commit_tests"]
    assert [e["to"] for e in out["history"]] == ["commit_tests", "implement"]
    assert out["history"][1]["sha"] == "abc"
    assert all(e["t"] == "t" for e in out["history"])
    assert out["node"] == "implement"
    assert out["pending"]["step_id"] == "u1-code-1"


def test_us7_advance_stops_at_a_decide_node():
    out = engine.advance(_state("tests_review"), CTX, {"tests_review": _h("CHANGES")})
    assert out["node"] == "tests_decide"
    assert out["pending"] == {"kind": "decide"}
    assert len(out["history"]) == 1


def test_us7_advance_does_not_mutate_the_input():
    s = _state("red_run")
    before = copy.deepcopy(s)
    h = {"red_run": _h("expected"), "commit_tests": _h("done")}
    out = engine.advance(s, CTX, h)
    assert json.dumps(s, sort_keys=True) == json.dumps(before, sort_keys=True)
    assert out is not s
