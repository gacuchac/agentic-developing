from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_path = Path(__file__).resolve().parents[1] / "scripts" / "hooks" / "subagent_record.py"

PENDING = {"kind": "agent", "agent": "qa", "step": "write", "step_id": "u3-write-1"}
STATE = {"task": "t", "node": "write_unit", "pending": PENDING}
CLAIM = {"session": "s1", "pid": 1, "pid_start": "x", "run": "", "checkout": "/c", "branch": "feature/t", "since": "now"}
RESULT = {"tests_added": ["tests/test_x.py"], "red_run": {"failed": ["test_x"], "reason_expected": True}}


@pytest.fixture
def hook():
    spec = importlib.util.spec_from_file_location("subagent_record", _path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _block(payload: str, label: str = "workflow-result") -> str:
    return f"```{label}\n{payload}\n```"


def _setup(tmp_path: Path, state: dict | None = STATE) -> tuple[Path, Path]:
    run = tmp_path / "run"
    run.mkdir()
    if state is not None:
        (run / "state.json").write_text(json.dumps(state))
    active = tmp_path / "active"
    active.mkdir()
    (active / "proj--t.json").write_text(json.dumps({**CLAIM, "run": str(run)}))
    return active, run


def _event(message: str, agent_type: str = "qa", session: str = "s1") -> str:
    return json.dumps({"session_id": session, "agent_id": "a1", "agent_type": agent_type,
                       "last_assistant_message": message})


class Recorder:
    def __init__(self, errors: list[str] | None = None):
        self.calls: list[tuple[Path, str, dict]] = []
        self.errors = errors or []

    def __call__(self, run: Path, step_id: str, result: dict) -> list[str]:
        self.calls.append((run, step_id, result))
        return self.errors


def test_us14_extract_result_parses_block(hook):
    assert hook.extract_result("done\n" + _block(json.dumps(RESULT))) == RESULT


def test_us14_extract_result_takes_last_block(hook):
    message = _block('{"a": 1}') + "\ntext\n" + _block('{"b": 2}')
    assert hook.extract_result(message) == {"b": 2}


def test_us14_extract_result_none_when_absent(hook):
    assert hook.extract_result("no block here") is None
    assert hook.extract_result(_block('{"a": 1}', label="json")) is None


def test_us14_extract_result_none_for_bad_json(hook):
    assert hook.extract_result(_block("{not json")) is None


def test_us14_extract_result_none_when_last_block_is_bad(hook):
    assert hook.extract_result(_block('{"a": 1}') + "\n" + _block("oops")) is None


def test_us14_step_id_of_reads_wf_step_line(hook):
    assert hook.step_id_of("wf-step: u3-write-1\nAgent: qa\n") == "u3-write-1"


def test_us14_step_id_of_none_without_line(hook):
    assert hook.step_id_of("Agent: qa\nDo it.\n") is None


def test_us14_main_records_result_for_pending_step(hook, tmp_path):
    active, run = _setup(tmp_path)
    rec = Recorder()
    assert hook.main(_event("ok\n" + _block(json.dumps(RESULT))), active, rec) == 0
    assert rec.calls == [(run, "u3-write-1", RESULT)]


def test_us14_main_records_implementer_for_implementer_step(hook, tmp_path):
    pending = {"kind": "agent", "agent": "implementer", "step": "implement", "step_id": "u3-impl-1"}
    active, run = _setup(tmp_path, {**STATE, "pending": pending})
    rec = Recorder()
    assert hook.main(_event(_block('{"ok": true}'), "implementer"), active, rec) == 0
    assert rec.calls == [(run, "u3-impl-1", {"ok": True})]


def test_us14_main_missing_block_records_nothing(hook, tmp_path):
    active, _ = _setup(tmp_path)
    rec = Recorder()
    assert hook.main(_event("finished, no block"), active, rec) == 0
    assert rec.calls == []


def test_us14_main_invalid_block_records_nothing(hook, tmp_path):
    active, _ = _setup(tmp_path)
    rec = Recorder()
    assert hook.main(_event(_block("{bad")), active, rec) == 0
    assert rec.calls == []


def test_us14_main_no_claim_records_nothing(hook, tmp_path):
    active, _ = _setup(tmp_path)
    rec = Recorder()
    assert hook.main(_event(_block("{}"), session="other"), active, rec) == 0
    assert rec.calls == []


def test_us14_main_non_workflow_agent_records_nothing(hook, tmp_path):
    active, _ = _setup(tmp_path)
    rec = Recorder()
    assert hook.main(_event(_block("{}"), "code-reviewer"), active, rec) == 0
    assert rec.calls == []


def test_us14_main_agent_other_than_pending_records_nothing(hook, tmp_path):
    active, _ = _setup(tmp_path)
    rec = Recorder()
    assert hook.main(_event(_block("{}"), "implementer"), active, rec) == 0
    assert rec.calls == []


def test_us14_main_no_pending_agent_step_records_nothing(hook, tmp_path):
    active, _ = _setup(tmp_path, {**STATE, "pending": {"kind": "auto"}})
    rec = Recorder()
    assert hook.main(_event(_block("{}")), active, rec) == 0
    assert rec.calls == []


def test_us14_main_refusal_returns_2_with_errors_on_stderr(hook, tmp_path, capsys):
    active, _ = _setup(tmp_path)
    rec = Recorder(["red_run.failed is empty", "tests_added missing"])
    assert hook.main(_event(_block(json.dumps(RESULT))), active, rec) == 2
    err = capsys.readouterr().err
    assert "red_run.failed is empty" in err and "tests_added missing" in err
    assert len(rec.calls) == 1
