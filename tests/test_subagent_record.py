from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_path = Path(__file__).resolve().parents[1] / "scripts" / "hooks" / "subagent_record.py"

PENDING = {"kind": "agent", "agent": "qa", "step": "write", "step_id": "u3-write-1"}
STATE = {"task": "t", "node": "write_unit", "pending": PENDING}
CLAIM = {
    "session": "s1",
    "pid": 1,
    "pid_start": "x",
    "run": "",
    "checkout": "/c",
    "branch": "feature/t",
    "since": "now",
}
RESULT = {
    "tests_added": ["tests/test_x.py"],
    "red_run": {"failed": ["test_x"], "reason_expected": True},
    "left_out": [],
}


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
    _register(active, "a1", run, PENDING["step_id"])
    return active, run


def _register(active: Path, agent_id: str, run: Path, step_id: str, agent: str = "qa") -> None:
    (active / "agents").mkdir(parents=True, exist_ok=True)
    entry = {"session": "s1", "run": str(run), "step_id": step_id, "agent": agent}
    (active / "agents" / f"{agent_id}.json").write_text(json.dumps(entry))


def _event(message: str, agent_type: str = "qa", session: str = "s1", agent_id: str = "a1") -> str:
    return json.dumps(
        {"session_id": session, "agent_id": agent_id, "agent_type": agent_type, "last_assistant_message": message}
    )


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
    _register(active, "a1", run, "u3-impl-1", "implementer")
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
    assert hook.main(_event(_block("{}"), agent_id="stranger"), active, rec) == 0
    assert rec.calls == []


def test_us21_main_two_tasks_pending_same_step_records_on_registered_run_only(hook, tmp_path):
    active, run_a = _setup(tmp_path)
    run_b = tmp_path / "run_b"
    run_b.mkdir()
    (run_b / "state.json").write_text(json.dumps(STATE))
    _register(active, "a2", run_b, PENDING["step_id"])
    rec = Recorder()
    assert hook.main(_event(_block(json.dumps(RESULT)), agent_id="a2"), active, rec) == 0
    assert rec.calls == [(run_b, "u3-write-1", RESULT)]


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


def _handback_event(message: str, hook_event: str = "PostToolUse", agent_type: str = "qa", last: str = "") -> str:
    return json.dumps(
        {
            "session_id": "s1",
            "agent_id": "a1",
            "agent_type": agent_type,
            "hook_event_name": hook_event,
            "tool_name": "SubagentHandback",
            "tool_input": {"message": message},
            "last_assistant_message": last,
        }
    )


@pytest.mark.parametrize("hook_event", ["PreToolUse", "PostToolUse"])
def test_us14_main_records_result_from_subagent_handback_message(hook, tmp_path, hook_event):
    active, run = _setup(tmp_path)
    rec = Recorder()
    assert hook.main(_handback_event("report\n" + _block(json.dumps(RESULT)), hook_event), active, rec) == 0
    assert rec.calls == [(run, "u3-write-1", RESULT)]


def test_us14_main_handback_refusal_returns_2(hook, tmp_path, capsys):
    active, _ = _setup(tmp_path)
    rec = Recorder(["tests_added missing"])
    assert hook.main(_handback_event(_block(json.dumps(RESULT))), active, rec) == 2
    assert "tests_added missing" in capsys.readouterr().err


def test_us14_main_handback_message_wins_when_last_message_empty_of_block(hook, tmp_path):
    active, run = _setup(tmp_path)
    rec = Recorder()
    event = _handback_event(_block('{"a": 1}'), last="thanks, done")
    assert hook.main(event, active, rec) == 0
    assert rec.calls == [(run, "u3-write-1", {"a": 1})]


def _nested_setup(tmp_path: Path, content, claim_session: str | None = "s1", name: str = "agent-n1.jsonl"):
    run = tmp_path / "run"
    run.mkdir(exist_ok=True)
    (run / "state.json").write_text(json.dumps(STATE))
    active = tmp_path / "active"
    active.mkdir(exist_ok=True)
    if claim_session is not None:
        (active / "claim.json").write_text(json.dumps({**CLAIM, "session": claim_session, "run": str(run)}))
    transcript = tmp_path / name
    records = [
        {"type": "user", "agentId": "n1", "sessionId": "s1", "message": {"role": "user", "content": content}},
        {"type": "assistant", "message": {"role": "assistant", "content": "working"}},
    ]
    transcript.write_text("\n".join(json.dumps(r) for r in records) + "\n")
    return active, run, transcript


def _nested_event(transcript: Path, session: str = "s1") -> str:
    return json.dumps(
        {
            "session_id": session,
            "agent_id": "n1",
            "agent_type": "qa",
            "agent_transcript_path": str(transcript),
            "last_assistant_message": "done\n" + _block(json.dumps(RESULT)),
        }
    )


def _prompt(run: Path) -> str:
    return f"wf-step: u3-write-1\nRun folder: {run}\nAgent: qa\n\nWrite the tests.\n"


def test_us21_nested_agent_result_recorded_from_transcript_prompt(hook, tmp_path):
    active, run, transcript = _nested_setup(tmp_path, "placeholder")
    transcript.write_text(json.dumps({"type": "user", "message": {"role": "user", "content": _prompt(run)}}) + "\n")
    rec = Recorder()
    assert hook.main(_nested_event(transcript), active, rec) == 0
    assert rec.calls == [(run, "u3-write-1", RESULT)]


def test_us21_nested_agent_prompt_as_text_parts_is_recorded(hook, tmp_path):
    active, run, transcript = _nested_setup(tmp_path, "placeholder")
    parts = [{"type": "text", "text": "wf-step: u3-write-1\n"}, {"type": "text", "text": f"Run folder: {run}\n"}]
    transcript.write_text(json.dumps({"type": "user", "message": {"role": "user", "content": parts}}) + "\n")
    rec = Recorder()
    assert hook.main(_nested_event(transcript), active, rec) == 0
    assert rec.calls == [(run, "u3-write-1", RESULT)]


def test_us21_nested_agent_run_held_by_other_session_or_nobody_records_nothing(hook, tmp_path):
    active, run, transcript = _nested_setup(tmp_path, "placeholder")
    transcript.write_text(json.dumps({"type": "user", "message": {"role": "user", "content": _prompt(run)}}) + "\n")
    rec = Recorder()
    assert hook.main(_nested_event(transcript), active, rec) == 0
    assert rec.calls == [(run, "u3-write-1", RESULT)]
    (active / "claim.json").write_text(json.dumps({**CLAIM, "session": "other", "run": str(run)}))
    assert hook.main(_nested_event(transcript), active, rec) == 0
    (active / "claim.json").unlink()
    assert hook.main(_nested_event(transcript), active, rec) == 0
    assert len(rec.calls) == 1


def test_us21_nested_agent_without_transcript_or_run_line_records_nothing(hook, tmp_path):
    active, run, transcript = _nested_setup(tmp_path, "placeholder")
    transcript.write_text(json.dumps({"type": "user", "message": {"role": "user", "content": _prompt(run)}}) + "\n")
    rec = Recorder()
    assert hook.main(_nested_event(transcript), active, rec) == 0
    assert rec.calls == [(run, "u3-write-1", RESULT)]
    transcript.write_text(
        json.dumps({"type": "user", "message": {"role": "user", "content": "wf-step: u3-write-1\n"}}) + "\n"
    )
    assert hook.main(_nested_event(transcript), active, rec) == 0
    transcript.unlink()
    assert hook.main(_nested_event(transcript), active, rec) == 0
    assert len(rec.calls) == 1


def test_us21_engine_python_is_the_workspace_venv_interpreter_when_present(hook, tmp_path):
    interpreter = tmp_path / ".venv" / "bin" / "python"
    interpreter.parent.mkdir(parents=True)
    interpreter.write_text("")
    assert hook.engine_python(tmp_path) == str(interpreter)


def test_us21_engine_python_falls_back_to_python3_without_a_venv(hook, tmp_path):
    assert hook.engine_python(tmp_path) == "python3"


OTHER = {"tests_added": ["tests/test_y.py"], "red_run": {"failed": ["test_y"], "reason_expected": True}, "left_out": []}
EXAMPLE = {"tests_added": ["x"], "red_run": {"failed": [], "reason_expected": False}, "left_out": []}


def _silent_event(transcript: Path) -> str:
    return json.dumps(
        {
            "session_id": "s1",
            "agent_id": "n1",
            "agent_type": "qa",
            "agent_transcript_path": str(transcript),
            "last_assistant_message": "",
        }
    )


def _record(role: str, parts) -> str:
    return json.dumps({"type": role, "message": {"role": role, "content": parts}})


def _handback(result: dict) -> list:
    return [{"type": "tool_use", "name": "SubagentHandback", "input": {"message": "Report\n" + _block(json.dumps(result))}}]


def _write_transcript(transcript: Path, run: Path, *assistant_records: str) -> None:
    prompt = _prompt(run) + "Reply with:\n" + _block(json.dumps(EXAMPLE)) + "\n"
    transcript.write_text("\n".join([_record("user", prompt), *assistant_records]) + "\n")


def test_us21_handback_call_block_in_transcript_is_recorded_not_the_prompt_example(hook, tmp_path):
    active, run, transcript = _nested_setup(tmp_path, "placeholder")
    _write_transcript(transcript, run, _record("assistant", _handback(OTHER)))
    rec = Recorder()
    assert hook.main(_silent_event(transcript), active, rec) == 0
    assert rec.calls == [(run, "u3-write-1", OTHER)]


def test_us21_prompt_example_block_alone_is_never_recorded_from_transcript(hook, tmp_path):
    active, run, transcript = _nested_setup(tmp_path, "placeholder")
    _write_transcript(transcript, run, _record("assistant", _handback(OTHER)))
    rec = Recorder()
    assert hook.main(_silent_event(transcript), active, rec) == 0
    _write_transcript(transcript, run, _record("assistant", [{"type": "text", "text": "no block here"}]))
    assert hook.main(_silent_event(transcript), active, rec) == 0
    assert rec.calls == [(run, "u3-write-1", OTHER)]


def test_us21_transcript_text_block_found_and_later_handback_block_wins(hook, tmp_path):
    active, run, transcript = _nested_setup(tmp_path, "placeholder")
    text = _record("assistant", [{"type": "text", "text": "Done\n" + _block(json.dumps(EXAMPLE | {"left_out": ["t"]}))}])
    _write_transcript(transcript, run, text)
    rec = Recorder()
    assert hook.main(_silent_event(transcript), active, rec) == 0
    assert rec.calls == [(run, "u3-write-1", EXAMPLE | {"left_out": ["t"]})]
    _write_transcript(transcript, run, text, _record("assistant", _handback(OTHER)))
    assert hook.main(_silent_event(transcript), active, rec) == 0
    assert rec.calls[1:] == [(run, "u3-write-1", OTHER)]


def _log_lines(active: Path) -> list[dict]:
    log = active / "recorder.log"
    return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []


def test_us30_logs_recorded_outcome(hook, tmp_path):
    active, run = _setup(tmp_path)
    message = _block(json.dumps(RESULT))

    code = hook.main(_event(message), active, lambda r, s, x: [])

    lines = _log_lines(active)
    assert code == 0
    assert len(lines) == 1
    assert lines[0]["outcome"] == "recorded"
    assert lines[0]["step"] == [str(run), "u3-write-1"]
    assert lines[0]["result"] is True
    assert lines[0]["agent_id"] == "a1"
    assert lines[0]["agent_type"] == "qa"
    assert lines[0]["session"] == "s1"
    assert lines[0]["transcript"] is False


def test_us30_logs_no_step_without_registry_entry(hook, tmp_path):
    active = tmp_path / "active"
    active.mkdir()

    hook.main(_event(_block(json.dumps(RESULT)), agent_id="ghost"), active, lambda r, s, x: [])

    lines = _log_lines(active)
    assert len(lines) == 1
    assert lines[0]["outcome"] == "no step"
    assert lines[0]["step"] is None


def test_us30_logs_no_result_when_no_block(hook, tmp_path):
    active, run = _setup(tmp_path)

    hook.main(_event("all done, no block"), active, lambda r, s, x: [])

    lines = _log_lines(active)
    assert len(lines) == 1
    assert lines[0]["outcome"] == "no result"
    assert lines[0]["step"] == [str(run), "u3-write-1"]
    assert lines[0]["result"] is False


def test_us30_logs_refused_and_still_returns_2(hook, tmp_path):
    active, _ = _setup(tmp_path)

    code = hook.main(_event(_block(json.dumps(RESULT))), active, lambda r, s, x: ["bad result"])

    lines = _log_lines(active)
    assert code == 2
    assert len(lines) == 1
    assert lines[0]["outcome"] == "refused"
    assert lines[0]["result"] is True


def test_us30_logs_bad_input_and_returns_0(hook, tmp_path):
    active = tmp_path / "active"
    active.mkdir()

    code = hook.main("not json {", active, lambda r, s, x: [])

    lines = _log_lines(active)
    assert code == 0
    assert len(lines) == 1
    assert lines[0]["outcome"] == "bad input"
