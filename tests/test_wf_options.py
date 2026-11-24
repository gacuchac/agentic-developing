"""US-11: wf shows the options a person or agent may take, and finds the repo and Ctx of a run."""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "workflow"))

import graph  # noqa: E402
import state as st  # noqa: E402
import wf  # noqa: E402


def _tree(tmp_path, project):
    ws = tmp_path / "Developing"
    run = ws / ".claude" / "runs" / project / "t1"
    run.mkdir(parents=True)
    return ws, run


def _ctx(ws, run, python=Path("/engine/venv/bin/python")):
    return SimpleNamespace(
        run=run,
        repo=ws,
        python=python,
        now=lambda: "t",
        diff=lambda r: "",
        file_at=lambda repo, path, sha: "x",
        log=lambda r, c: None,
    )


def _agent_state():
    s = st.new_state("t", "b", "l")
    s["node"] = "qa_write"
    s["pending"] = {"kind": "agent", "agent": "qa", "step": "write", "step_id": "u1-write-1"}
    return s


def _decide_state(wrong_dismissals=0):
    s = st.new_state("t", "b", "l")
    s["node"], s["pending"] = "tests_decide", {"kind": "decide"}
    s = st.with_entry(
        s,
        {
            "node": "tests_review",
            "outcome": "CHANGES",
            "reviews": [{"pass": "tests", "fails": ["T2"], "verdict": "CHANGES"}],
        },
        "n",
    )
    for i in range(wrong_dismissals):
        s = st.with_entry(
            s,
            {
                "node": "tests_decide",
                "decision": "wrong",
                "to": "verify",
                "evidence": {"findings": [f"W{i}"]},
                "passes": {f"W{i}": "tests"},
            },
            "n",
        )
    return s


def test_us11_repo_for_workspace_run_is_the_workspace(tmp_path):
    ws, run = _tree(tmp_path, "Developing")
    assert wf.repo_for(run) == ws


def test_us11_repo_for_project_run_is_the_project_folder(tmp_path):
    ws, run = _tree(tmp_path, "proj")
    assert wf.repo_for(run) == ws / "proj"


def test_us11_options_at_agent_step_offer_one_launch_with_prompt(tmp_path):
    ws, run = _tree(tmp_path, "Developing")
    (run / "unit.md").write_text("do the unit")
    out = wf.options_view(_agent_state(), _ctx(ws, run))
    assert len(out) == 1
    o = out[0]
    assert (o["id"], o["kind"], o["agent"], o["step_id"]) == ("launch", "agent", "qa", "u1-write-1")
    assert o["prompt"].startswith("wf-step:")
    assert "u1-write-1" in o["prompt"]


def test_us11_options_use_prompt_template_file_when_present(tmp_path):
    ws, run = _tree(tmp_path, "Developing")
    (run / "unit.md").write_text("do the unit")
    prompts = ws / ".claude" / "workflow" / "prompts"
    prompts.mkdir(parents=True)
    (prompts / "qa-write.md").write_text("wf-step: {step_id} CUSTOMTEMPLATEMARK")
    o = wf.options_view(_agent_state(), _ctx(ws, run))[0]
    assert "CUSTOMTEMPLATEMARK" in o["prompt"]
    assert o["prompt"].startswith("wf-step:")


def test_us11_options_prompt_carries_last_refusal_error(tmp_path):
    ws, run = _tree(tmp_path, "Developing")
    (run / "unit.md").write_text("do the unit")
    s = st.with_entry(_agent_state(), {"node": "qa_write", "error": "tests_added missing zzz-refusal"}, "n")
    o = wf.options_view(s, _ctx(ws, run))[0]
    assert "zzz-refusal" in o["prompt"]


def test_us11_options_at_decide_list_each_legal_option_with_evidence_keys(tmp_path):
    ws, run = _tree(tmp_path, "Developing")
    out = wf.options_view(_decide_state(), _ctx(ws, run))
    by = {o["id"]: o for o in out}
    assert set(by) == {"correct", "overstated", "wrong", "escalate"}
    assert all(o["kind"] == "decide" for o in out)
    assert by["correct"]["to"] == "qa_fix"
    assert by["overstated"]["to"] == "verify"
    assert by["wrong"]["to"] == "verify"
    assert by["correct"]["evidence"] == ["findings"]
    assert by["overstated"]["evidence"] == ["findings"]
    assert by["wrong"]["evidence"] == ["findings"]
    assert by["escalate"]["evidence"] == ["question"]
    assert by["escalate"]["to"] == "user"


def test_us11_options_drop_wrong_after_two_wrong_dismissals(tmp_path):
    ws, run = _tree(tmp_path, "Developing")
    assert graph.WRONG_CAP == 2
    ids = {o["id"] for o in wf.options_view(_decide_state(2), _ctx(ws, run))}
    assert "wrong" not in ids
    assert {"correct", "overstated"} <= ids


def test_us11_options_keep_wrong_after_one_wrong_dismissal(tmp_path):
    ws, run = _tree(tmp_path, "Developing")
    ids = {o["id"] for o in wf.options_view(_decide_state(1), _ctx(ws, run))}
    assert "wrong" in ids


def test_us11_options_at_done_are_empty(tmp_path):
    ws, run = _tree(tmp_path, "Developing")
    s = st.new_state("t", "b", "l")
    s["node"], s["pending"] = "done", {"kind": "end"}
    assert wf.options_view(s, _ctx(ws, run)) == []


def test_us11_default_ctx_fields_are_callable_or_paths_and_repo_matches(tmp_path):
    ws, run = _tree(tmp_path, "proj")
    ctx = wf.default_ctx(run)
    values = vars(ctx) if hasattr(ctx, "__dict__") else {f: getattr(ctx, f) for f in ctx.__dataclass_fields__}
    assert values
    for name, v in values.items():
        assert callable(v) or isinstance(v, Path), name
    assert ctx.repo == wf.repo_for(run) == ws / "proj"
    assert ctx.run == run


def test_us38_default_ctx_subtract_record_is_the_hook_record(tmp_path):
    _, run = _tree(tmp_path, "proj")
    expected = {"kind": "subtract", "sha": "abc", "tests_touched": ["t.py"], "suite_failed": []}
    assert wf.default_ctx(run).subtract_record("abc", ["t.py"], []) == expected


def test_us11_default_ctx_collect_review_takes_only_the_handle(tmp_path):
    ws, run = _tree(tmp_path, "proj")
    log = tmp_path / "pass.log"
    log.write_text("saved: /tmp/review-x.md\n")
    handle = {"pid": 2**22 + 12345, "log": str(log)}
    assert wf.default_ctx(run).collect_review(handle) == Path("/tmp/review-x.md")


def _save_checkout(run, checkout):
    s = st.new_state("t", "b", "l")
    s["checkout"] = checkout
    st.save(run, s)


def test_us19_default_ctx_repo_is_stored_checkout(tmp_path):
    _, run = _tree(tmp_path, "proj")
    worktree = tmp_path / "wt"
    _save_checkout(run, str(worktree))
    assert wf.default_ctx(run).repo == worktree


def test_us19_default_ctx_explicit_checkout_wins_over_state(tmp_path):
    _, run = _tree(tmp_path, "proj")
    _save_checkout(run, str(tmp_path / "stored"))
    other = tmp_path / "given"
    assert wf.default_ctx(run, other).repo == other
    assert wf.default_ctx(tmp_path / "Developing" / ".claude" / "runs" / "proj" / "none", other).repo == other


def _fix_section(prompt):
    lines = prompt.splitlines()
    heads = [i for i, line in enumerate(lines) if line.lstrip("# ").rstrip(":").strip() == "What to fix"]
    return [] if not heads else [line.strip() for line in lines[heads[-1] + 1 :]]


def _fix_state(entries, agent, step):
    s = st.new_state("t", "b", "l")
    for e in entries:
        s = st.with_entry(s, e, "n")
    s["node"] = "implement" if agent == "implementer" else "qa_fix"
    s["pending"] = {"kind": "agent", "agent": agent, "step": step, "step_id": "u1-x-1"}
    return s


def test_us17_correct_decision_prompt_has_what_to_fix_with_finding_line_and_reason(tmp_path):
    ws, run = _tree(tmp_path, "Developing")
    (run / "unit.md").write_text("do the unit")
    other, main = run / "review-other.md", run / "review-impl.md"
    other.write_text("O1: FAIL — unrelated\n")
    main.write_text("# Review\nI0: PASS — fine\nI1: FAIL — the alias is wrong\nI2: FAIL — other thing\n")
    review = {
        "node": "impl_review",
        "outcome": "CHANGES",
        "reviews": [
            {"pass": "a", "review": str(other), "verdict": "CHANGES", "fails": ["O1"]},
            {"pass": "b", "review": str(main), "verdict": "CHANGES", "fails": ["I1", "I2"]},
        ],
    }
    decision = {
        "node": "impl_decide",
        "decision": "correct",
        "evidence": {"findings": [{"id": "I1", "reason": "the alias maps to the wrong name"}]},
        "to": "implement",
    }
    s = _fix_state([review, decision], "implementer", "code")
    prompt = wf.options_view(s, _ctx(ws, run))[0]["prompt"]
    sec = _fix_section(prompt)
    assert "I1: FAIL — the alias is wrong" in sec
    assert "Decision: the alias maps to the wrong name" in sec
    assert not any(line.startswith(("I2:", "O1:")) for line in sec)


def test_us17_tests_wrong_decision_prompt_has_test_id_and_plan_quote(tmp_path):
    ws, run = _tree(tmp_path, "Developing")
    (run / "unit.md").write_text("do the unit")
    decision = {
        "node": "fail_decide",
        "decision": "tests_wrong",
        "evidence": {"test": "tests/test_a.py::test_x", "quote": "the alias maps to beta"},
        "to": "qa_fix",
    }
    s = _fix_state([decision], "qa", "fix")
    sec = _fix_section(wf.options_view(s, _ctx(ws, run))[0]["prompt"])
    assert "Test: tests/test_a.py::test_x" in sec
    assert "Plan line: the alias maps to beta" in sec


def test_us17_code_wrong_decision_prompt_lists_failing_tests(tmp_path):
    ws, run = _tree(tmp_path, "Developing")
    (run / "unit.md").write_text("do the unit")
    decision = {
        "node": "fail_decide",
        "decision": "code_wrong",
        "evidence": {"tests": ["tests/test_a.py::test_x", "tests/test_a.py::test_y"]},
        "to": "implement",
    }
    s = _fix_state([decision], "implementer", "code")
    sec = _fix_section(wf.options_view(s, _ctx(ws, run))[0]["prompt"])
    assert "Failing tests: tests/test_a.py::test_x, tests/test_a.py::test_y" in sec


def test_us17_first_implement_prompt_has_no_section_but_one_after_a_decision(tmp_path):
    ws, run = _tree(tmp_path, "Developing")
    (run / "unit.md").write_text("do the unit")
    decision = {"node": "fail_decide", "decision": "code_wrong", "evidence": {"tests": ["t::a"]}, "to": "implement"}
    plain = wf.options_view(_fix_state([], "implementer", "code"), _ctx(ws, run))[0]["prompt"]
    fixed = wf.options_view(_fix_state([decision], "implementer", "code"), _ctx(ws, run))[0]["prompt"]
    assert _fix_section(plain) == []
    assert "Failing tests: t::a" in _fix_section(fixed)


PROMPT_TEMPLATES = ["qa-write.md", "qa-fix.md", "implementer-code.md", "implementer-subtract.md"]


def _lines_after_run_folder(prompt):
    lines = prompt.splitlines()
    i = next(n for n, line in enumerate(lines) if line.startswith("Run folder:"))
    return lines[i + 1 : i + 3]


def test_us17_qa_write_prompt_names_plan_and_python_after_run_folder(tmp_path):
    ws, run = _tree(tmp_path, "Developing")
    (run / "unit.md").write_text("do the unit")
    s = _agent_state()
    s["plan"] = "myplan.md"
    py = Path("/some/engine/python")
    prompt = wf.options_view(s, _ctx(ws, run, py))[0]["prompt"]
    assert _lines_after_run_folder(prompt) == [f"Plan: {run / 'myplan.md'}", f"Python: {py}"]


def test_us17_implementer_prompt_names_plan_and_python_after_run_folder(tmp_path):
    ws, run = _tree(tmp_path, "Developing")
    (run / "unit.md").write_text("do the unit")
    s = _agent_state()
    s["pending"] = {"kind": "agent", "agent": "implementer", "step": "code", "step_id": "u1-code-1"}
    py = Path("/another/python")
    prompt = wf.options_view(s, _ctx(ws, run, py))[0]["prompt"]
    assert _lines_after_run_folder(prompt) == [f"Plan: {run / 'plan.md'}", f"Python: {py}"]


def test_us17_template_prompt_gets_plan_and_python_after_run_folder(tmp_path):
    ws, run = _tree(tmp_path, "Developing")
    (run / "unit.md").write_text("do the unit")
    prompts = ws / ".claude" / "workflow" / "prompts"
    prompts.mkdir(parents=True)
    (prompts / "qa-write.md").write_text("wf-step: {step_id}\nRun folder: {run}\nAgent: qa\n")
    py = Path("/tpl/python")
    prompt = wf.options_view(_agent_state(), _ctx(ws, run, py))[0]["prompt"]
    assert _lines_after_run_folder(prompt) == [f"Plan: {run / 'plan.md'}", f"Python: {py}"]


@pytest.mark.parametrize("name", PROMPT_TEMPLATES)
def test_us17_template_names_python_line_and_plan_approach(name):
    text = (Path(__file__).resolve().parent.parent / ".claude" / "workflow" / "prompts" / name).read_text()
    assert "`Python:` line" in text
    assert "-m pytest -q" in text
    assert "Approach" in text
    assert "Contracts" in text


def test_us17_implementer_template_states_the_disputed_entry_format():
    text = (Path(__file__).resolve().parent.parent / ".claude/workflow/prompts/implementer-code.md").read_text()
    assert "<test id>: <the plan line it contradicts>" in text
