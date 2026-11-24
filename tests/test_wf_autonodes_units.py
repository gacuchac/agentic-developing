"""Tests of scripts/workflow/autonodes.py: write_unit and next_unit handlers."""

import autonodes
import state
import units

PLAN = """# Plan

## Build

### 1. First thing (US-1)
Lane: fast
Do the first thing.

### 2. Second thing (US-2)
Lane: full
Do the second thing.

### 3. Third thing (US-3)
Do the third thing.
"""

P3_LINE = "P3: FAIL - contract of `foo` changed without approval"
REVIEW = f"P1: PASS\nP2: PASS\n{P3_LINE}\nP4: PASS\n"


def _ctx(run):
    def nope(*a, **k):
        raise AssertionError("unexpected call")

    return autonodes.Ctx(
        run=run,
        repo=run,
        python=run / "py",
        start_review=nope,
        collect_review=nope,
        run_review=nope,
        tests=nope,
        touched=nope,
        source=nope,
        commit=nope,
        evidence=nope,
        diff=nope,
        file_at=nope,
        log=lambda *a: None,
        now=lambda: "t0",
    )


def _state(run, unit=1, fix=0, stage="build"):
    (run / "plan.md").write_text(PLAN)
    s = state.new_state("t", "feature/x", "launch")
    return {**s, "unit": unit, "fix": fix, "stage": stage, "head": "abc123"}


def test_us6_write_unit_writes_plan_unit_two(tmp_path):
    out, _, _ = autonodes.HANDLERS["write_unit"](_state(tmp_path, unit=2), _ctx(tmp_path))
    assert out == "done"
    assert (tmp_path / "unit.md").read_text().strip() == units.plan_units(PLAN)[1].strip()


def test_us6_write_unit_writes_first_unit(tmp_path):
    autonodes.HANDLERS["write_unit"](_state(tmp_path, unit=1), _ctx(tmp_path))
    text = (tmp_path / "unit.md").read_text()
    assert text.startswith("### 1. First thing")
    assert "Second thing" not in text


def test_us6_write_unit_fix_after_branch_decide_holds_fail_line(tmp_path):
    s = _state(tmp_path, unit=2, fix=1)
    (tmp_path / "review-principles-1.md").write_text(REVIEW)
    s["history"] = [
        {
            "t": "t1",
            "unit": "2",
            "node": "branch_reviews",
            "verdict": "CHANGES",
            "reviews": [
                {
                    "pass": "principles",
                    "review": "review-principles-1.md",
                    "verdict": "CHANGES",
                    "fails": ["P3"],
                    "dropped": [],
                }
            ],
        },
        {"t": "t2", "unit": "2", "node": "branch_decide", "decision": "correct", "evidence": {"findings": ["P3"]}},
    ]
    out, _, _ = autonodes.HANDLERS["write_unit"](s, _ctx(tmp_path))
    assert out == "done"
    text = (tmp_path / "unit.md").read_text()
    assert text.splitlines()[0] == units.plan_units(PLAN)[1].splitlines()[0]
    assert "Fix: principles P3 on abc123" in text
    assert P3_LINE in text
    assert "P1: PASS" not in text


def test_us6_next_unit_more_advances_and_resets_fix(tmp_path):
    s = _state(tmp_path, unit=2, fix=1)
    out, _, new = autonodes.HANDLERS["next_unit"](s, _ctx(tmp_path))
    assert out == "more"
    assert new["unit"] == 3
    assert new["fix"] == 0


def test_us6_next_unit_last_on_final_unit(tmp_path):
    out, _, _ = autonodes.HANDLERS["next_unit"](_state(tmp_path, unit=3), _ctx(tmp_path))
    assert out == "last"


def test_us6_next_unit_finished_in_finish_stage(tmp_path):
    out, _, _ = autonodes.HANDLERS["next_unit"](_state(tmp_path, unit=1, stage="finish"), _ctx(tmp_path))
    assert out == "finished"


def test_us6_write_unit_fix_after_full_decide_holds_failing_tests(tmp_path):
    s = _state(tmp_path, unit=2, fix=1)
    s["history"] = [
        {"t": "t1", "unit": "2", "node": "full_suite", "outcome": "fail", "failed": ["tests/t.py::test_a"]},
        {
            "t": "t2",
            "unit": "2",
            "node": "full_decide",
            "decision": "code_wrong",
            "evidence": {"tests": ["tests/t.py::test_a"]},
        },
    ]
    out, _, _ = autonodes.HANDLERS["write_unit"](s, _ctx(tmp_path))
    assert out == "done"
    text = (tmp_path / "unit.md").read_text()
    assert text.splitlines()[0] == units.plan_units(PLAN)[1].splitlines()[0]
    assert "Fix: full-suite tests/t.py::test_a on abc123" in text
    assert text.splitlines()[-1] == "tests/t.py::test_a"
