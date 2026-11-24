from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_path = Path(__file__).resolve().parents[1] / "scripts" / "hooks" / "launch_guard.py"
_spec = importlib.util.spec_from_file_location("launch_guard", _path)
guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard)

PENDING = {"kind": "agent", "agent": "qa", "step": "write", "step_id": "u3-write-1"}
STATE = {"task": "t", "node": "write_unit", "pending": PENDING}
CLAIM = {"session": "s1", "pid": 1, "pid_start": "x", "run": "", "checkout": "/c", "branch": "feature/t", "since": "now"}


def _agent(agent: str, step_id: str | None, extra: dict | None = None) -> dict:
    prompt = "Do the work.\n" if step_id is None else f"wf-step: {step_id}\nAgent: {agent}\nDo the work.\n"
    return {"session_id": "s1", "tool_name": "Agent",
            "tool_input": {"subagent_type": agent, "prompt": prompt, "description": "d"}, **(extra or {})}


def _bash(command: str, sub: bool) -> dict:
    event = {"session_id": "s1", "tool_name": "Bash", "tool_input": {"command": command}}
    return {**event, "agent_id": "a1"} if sub else event


def test_us14_allows_pending_agent_with_matching_step_id():
    assert guard.decide(_agent("qa", "u3-write-1"), CLAIM, STATE)[0] is True


def test_us14_denies_wrong_step_id_naming_pending_step_and_agent():
    allowed, reason = guard.decide(_agent("qa", "u3-write-2"), CLAIM, STATE)
    assert allowed is False
    assert "u3-write-1" in reason and "qa" in reason


def test_us14_denies_missing_step_line():
    assert guard.decide(_agent("qa", None), CLAIM, STATE)[0] is False


def test_us14_denies_wrong_agent_even_with_matching_id():
    assert guard.decide(_agent("implementer", "u3-write-1"), CLAIM, STATE)[0] is False


def test_us14_allows_reviewer_and_explore_in_any_state():
    for name in ("code-reviewer", "Explore"):
        assert guard.decide(_agent(name, None), CLAIM, STATE)[0] is True


def test_us14_allows_workflow_agent_without_claim():
    assert guard.decide(_agent("qa", None), None, None)[0] is True


def test_us14_allows_workflow_agent_when_pending_is_not_an_agent_step():
    state = {**STATE, "pending": {"kind": "auto"}}
    assert guard.decide(_agent("implementer", None), CLAIM, state)[0] is True


def test_us14_non_agent_tool_is_allowed():
    event = {"session_id": "s1", "tool_name": "Read", "tool_input": {"file_path": "/x"}}
    assert guard.decide(event, CLAIM, STATE)[0] is True


def test_us14_denies_wf_release_from_subagent():
    assert guard.decide(_bash("python3 scripts/wf.py release t", True), CLAIM, STATE)[0] is False


def test_us14_allows_wf_release_from_main_session():
    assert guard.decide(_bash("python3 scripts/wf.py release t", False), CLAIM, STATE)[0] is True


def test_us14_allows_other_bash_from_subagent():
    assert guard.decide(_bash("ls", True), CLAIM, STATE)[0] is True


def _setup(tmp_path: Path, state: dict | None = STATE) -> Path:
    run = tmp_path / "run"
    run.mkdir()
    if state is not None:
        (run / "state.json").write_text(json.dumps(state))
    active = tmp_path / "active"
    active.mkdir()
    (active / "proj--t.json").write_text(json.dumps({**CLAIM, "run": str(run)}))
    return active


def test_us14_main_denies_off_graph_launch_with_exit_2(tmp_path, capsys):
    active = _setup(tmp_path)
    assert guard.main(json.dumps(_agent("qa", "u9-write-1")), active) == 2
    assert "u3-write-1" in capsys.readouterr().err


def test_us14_main_allows_on_graph_launch(tmp_path):
    active = _setup(tmp_path)
    assert guard.main(json.dumps(_agent("qa", "u3-write-1")), active) == 0


def test_us14_main_ignores_other_sessions_claims(tmp_path):
    active = _setup(tmp_path)
    event = {**_agent("qa", None), "session_id": "other"}
    assert guard.main(json.dumps(event), active) == 0


def test_us14_main_allows_unreadable_input(tmp_path):
    assert guard.main("not json", _setup(tmp_path)) == 0


def test_us14_main_allows_when_state_unreadable(tmp_path):
    active = _setup(tmp_path, state=None)
    assert guard.main(json.dumps(_agent("qa", None)), active) == 0
