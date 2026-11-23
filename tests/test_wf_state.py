"""Tests of scripts/workflow/state.py: create, load and save the state."""
import json

import state


def test_us6_new_state_has_every_key():
    s = state.new_state("task-1", "feature/x", "launch")
    assert s["task"] == "task-1"
    assert s["branch"] == "feature/x"
    assert s["launch"] == "launch"
    assert s["stage"] == "build"
    assert s["unit"] == 1
    assert s["node"] == "write_unit"
    assert s["round"] == 1
    assert s["pending"] == {"kind": "auto"}
    assert s["history"] == []
    assert s["plan"] == "plan.md"
    assert s["fix"] == 0
    assert s["head"] is None
    assert s["mode"] == "sequential"


def test_us6_new_state_accepts_plan_and_mode():
    s = state.new_state("t", "b", "l", plan="plan-phase-a.md", mode="parallel")
    assert s["plan"] == "plan-phase-a.md"
    assert s["mode"] == "parallel"


def test_us6_new_state_histories_are_not_shared():
    a = state.new_state("t", "b", "l")
    a["history"].append({"x": 1})
    assert state.new_state("t", "b", "l")["history"] == []


def test_us6_save_then_load_round_trips(tmp_path):
    s = state.new_state("t", "b", "l")
    s["history"].append({"kind": "x", "t": "now", "unit": "1"})
    state.save(tmp_path, s)
    assert state.load(tmp_path) == s


def test_us6_save_writes_indented_json_and_leaves_no_temp_file(tmp_path):
    state.save(tmp_path, state.new_state("t", "b", "l"))
    text = (tmp_path / "state.json").read_text()
    assert "\n  " in text
    assert json.loads(text)["task"] == "t"
    assert [p.name for p in tmp_path.iterdir()] == ["state.json"]


def test_us6_save_overwrites_previous_state(tmp_path):
    s = state.new_state("t", "b", "l")
    state.save(tmp_path, s)
    s["unit"] = 2
    state.save(tmp_path, s)
    assert state.load(tmp_path)["unit"] == 2


def test_us6_unit_label_without_fix():
    assert state.unit_label({"unit": 3, "fix": 0}) == "3"


def test_us6_unit_label_with_fix():
    assert state.unit_label({"unit": 3, "fix": 1}) == "3-fix1"
