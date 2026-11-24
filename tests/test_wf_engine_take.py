"""US-9: engine.take records a decision only with valid evidence and moves the task to the right node."""

import copy
import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "workflow"))

import engine  # noqa: E402
import graph  # noqa: E402
import state as st  # noqa: E402


def _ctx(tmp_path, logged):
    return SimpleNamespace(
        run=tmp_path,
        repo=tmp_path,
        now=lambda: "t",
        diff=lambda r: "",
        file_at=lambda repo, path, sha: "x",
        log=lambda run, cells: logged.append((run, cells)),
    )


def _h(outcome, entry=None):
    return lambda state, ctx: (outcome, dict(entry or {}), state)


def _state(node, unit=1):
    s = st.new_state("t", "b", "l")
    s["unit"], s["node"] = unit, node
    s["pending"] = {"kind": "decide"}
    return s


def _review(s, node, passname, fails):
    entry = {
        "node": node,
        "outcome": "CHANGES",
        "reviews": [{"pass": passname, "fails": list(fails), "verdict": "CHANGES"}],
    }
    return st.with_entry(s, entry, "n")


def test_us9_correct_finding_goes_back_to_qa_fix(tmp_path):
    logged = []
    s = _review(_state("tests_decide"), "tests_review", "tests", ["T2"])
    out, errors = engine.take(s, "correct", {"findings": ["T2"]}, _ctx(tmp_path, logged), {})
    assert errors == []
    assert out["node"] == "qa_fix"
    assert out["pending"]["kind"] == "agent"
    e = out["history"][-1]
    assert (e["node"], e["decision"], e["to"]) == ("tests_decide", "correct", "qa_fix")
    assert e["evidence"] == {"findings": ["T2"]}
    assert e["t"] == "t"


def test_us9_correct_with_unknown_finding_is_refused_and_state_unchanged(tmp_path):
    logged = []
    s = _review(_state("tests_decide"), "tests_review", "tests", ["T2"])
    before = copy.deepcopy(s)
    out, errors = engine.take(s, "correct", {"findings": ["T9"]}, _ctx(tmp_path, logged), {})
    assert errors
    assert any("T9" in e for e in errors)
    assert json.dumps(out, sort_keys=True) == json.dumps(before, sort_keys=True)
    assert logged == []


def test_us9_illegal_option_names_the_legal_ones(tmp_path):
    logged = []
    s = _review(_state("tests_decide"), "tests_review", "tests", ["T2"])
    before = copy.deepcopy(s)
    out, errors = engine.take(s, "code_wrong", {"tests": ["x"]}, _ctx(tmp_path, logged), {})
    assert errors
    text = " ".join(errors)
    assert "correct" in text and "overstated" in text
    assert out == before
    assert logged == []


def test_us9_decision_at_a_non_decide_node_is_refused(tmp_path):
    logged = []
    s = st.new_state("t", "b", "l")
    s["node"], s["pending"] = "qa_write", {"kind": "agent"}
    out, errors = engine.take(s, "escalate", {"question": "q?"}, _ctx(tmp_path, logged), {})
    assert errors
    assert out == s
    assert logged == []


def test_us9_escalate_waits_at_user_with_the_question(tmp_path):
    logged = []
    s = _review(_state("tests_decide"), "tests_review", "tests", ["T2"])
    out, errors = engine.take(s, "escalate", {"question": "Which way?"}, _ctx(tmp_path, logged), {})
    assert errors == []
    assert out["node"] == "user"
    assert out["pending"]["kind"] == "user"
    assert out["pending"]["from"] == "tests_decide"
    assert "Which way?" in out["pending"]["reason"]
    assert out["history"][-1]["to"] == "user"


def test_us9_dismissing_every_fail_is_needed_before_the_task_moves_on(tmp_path):
    logged = []
    ctx = _ctx(tmp_path, logged)
    h = {"verify": _h("fail")}
    s = _review(_state("tests_decide"), "tests_review", "tests", ["T1", "T2"])
    ev1 = {"findings": [{"id": "T1", "reason": "cosmetic only"}]}
    s, errors = engine.take(s, "overstated", ev1, ctx, h)
    assert errors == []
    assert s["node"] == "tests_decide"
    assert s["pending"] == {"kind": "decide"}
    assert s["history"][-1]["to"] == "tests_decide"
    assert s["history"][-1]["passes"] == {"T1": "tests"}
    ev2 = {"findings": [{"id": "T2", "reason": "also cosmetic"}]}
    s, errors = engine.take(s, "overstated", ev2, ctx, h)
    assert errors == []
    assert s["node"] == "fail_decide"
    decided = [e for e in s["history"] if e.get("decision")]
    assert decided[-1]["to"] == "verify"
    assert decided[-1]["passes"] == {"T2": "tests"}
    assert len(logged) == 2


def test_us9_correct_at_branch_decide_starts_fix_round_one(tmp_path):
    logged = []
    s = _review(_state("branch_decide", unit=3), "branch_reviews", "principles", ["P3"])
    h = {"write_unit": _h("done")}
    out, errors = engine.take(s, "correct", {"findings": ["P3"]}, _ctx(tmp_path, logged), h)
    assert errors == []
    assert out["fix"] == 1
    assert st.unit_label(out) == "3-fix1"
    assert out["node"] == "qa_write"


def test_us9_user_continue_to_implement_resets_the_round_cap(tmp_path):
    logged = []
    s = _state("impl_decide")
    for _ in range(3):
        s = st.with_entry(s, {"node": "impl_decide", "decision": "correct", "to": "implement"}, "n")
    s = engine.enter(s, "user", "stuck")
    assert graph.back_rounds(s["history"], "implement") == 3
    ev = {"user_said": "carry on", "to": "implement"}
    out, errors = engine.take(s, "user_continue", ev, _ctx(tmp_path, logged), {})
    assert errors == []
    assert out["node"] == "implement"
    assert out["history"][-1]["by"] == "user"
    assert out["history"][-1]["to"] == "implement"
    assert graph.back_rounds(out["history"], "implement") == 0
    assert out["pending"]["kind"] == "agent"


def test_us9_log_is_called_once_per_accepted_decision_and_never_for_a_refused_one(tmp_path):
    logged = []
    ctx = _ctx(tmp_path, logged)
    s = _review(_state("tests_decide"), "tests_review", "tests", ["T2"])
    engine.take(s, "correct", {"findings": ["T9"]}, ctx, {})
    assert logged == []
    engine.take(s, "correct", {"findings": ["T2"]}, ctx, {})
    assert len(logged) == 1
    assert logged[0][0] == tmp_path


def _disputed_state(tmp_path, disputed):
    (tmp_path / "plan.md").write_text("a before b\nsecond line\n")
    s = _state("fail_decide")
    entry = {"node": "verify", "outcome": "fail", "failed": [], "disputed": disputed, "touched": []}
    return st.with_entry(s, entry, "n")


def test_us17_tests_wrong_names_a_disputed_test_by_its_id(tmp_path):
    s = _disputed_state(tmp_path, ["tests/t.py::test_x: plan line 'a before b'"])
    ev = {"test": "tests/t.py::test_x", "quote": "a before b"}
    out, errors = engine.take(s, "tests_wrong", ev, _ctx(tmp_path, []), {})
    assert errors == []
    assert out["history"][-1]["decision"] == "tests_wrong"
    assert out["node"] == "qa_fix"


def test_us17_disputed_entry_without_colon_space_is_accepted_as_written_and_others_by_id(tmp_path):
    bare = "tests/t.py::test_bare"
    s = _disputed_state(tmp_path, [bare, "tests/t.py::test_y: contradicts 'second line'"])
    ctx = _ctx(tmp_path, [])
    _, errors = engine.take(s, "tests_wrong", {"test": bare, "quote": "a before b"}, ctx, {})
    assert errors == []
    _, errors = engine.take(s, "tests_wrong", {"test": "tests/t.py::test_y", "quote": "second line"}, ctx, {})
    assert errors == []

