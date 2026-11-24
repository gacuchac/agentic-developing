"""US-11: wf shows the options a person or agent may take, and finds the repo and Ctx of a run."""

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "workflow"))

import graph  # noqa: E402
import state as st  # noqa: E402
import wf  # noqa: E402


def _tree(tmp_path, project):
    ws = tmp_path / "Developing"
    run = ws / ".claude" / "runs" / project / "t1"
    run.mkdir(parents=True)
    return ws, run


def _ctx(ws, run):
    return SimpleNamespace(
        run=run, repo=ws, now=lambda: "t", diff=lambda r: "", file_at=lambda repo, path, sha: "x", log=lambda r, c: None
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


def test_us11_default_ctx_collect_review_takes_only_the_handle(tmp_path):
    ws, run = _tree(tmp_path, "proj")
    log = tmp_path / "pass.log"
    log.write_text("saved: /tmp/review-x.md\n")
    handle = {"pid": 2**22 + 12345, "log": str(log)}
    assert wf.default_ctx(run).collect_review(handle) == Path("/tmp/review-x.md")
