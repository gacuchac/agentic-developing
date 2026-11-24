import importlib.util
import json
from pathlib import Path

import pytest

_path = Path(__file__).resolve().parents[1] / "scripts" / "hooks" / "agent_registry.py"


@pytest.fixture
def reg():
    spec = importlib.util.spec_from_file_location("agent_registry", _path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


PROMPT = "wf-step: u5-write-1\nRun folder: /runs/P/task\nAgent: qa\nWrite tests."


def _event(**over):
    event = {
        "session_id": "sess-1",
        "tool_name": "Agent",
        "tool_input": {"prompt": PROMPT, "subagent_type": "qa"},
        "tool_response": {"agentId": "abc123"},
    }
    event.update(over)
    return event


def test_us20_full_launch_event_gives_entry(reg):
    assert reg.entry_from(_event()) == (
        "abc123.json",
        {"session": "sess-1", "run": "/runs/P/task", "step_id": "u5-write-1", "agent": "qa"},
    )


def test_us20_missing_agent_id_gives_none(reg):
    assert reg.entry_from(_event(tool_response={})) is None


def test_us20_prompt_without_wf_step_gives_none(reg):
    prompt = "Run folder: /runs/P/task\nDo it."
    assert reg.entry_from(_event(tool_input={"prompt": prompt, "subagent_type": "qa"})) is None


def test_us20_prompt_without_run_folder_gives_none(reg):
    prompt = "wf-step: u5-write-1\nDo it."
    assert reg.entry_from(_event(tool_input={"prompt": prompt, "subagent_type": "qa"})) is None


def test_us20_other_tool_gives_none(reg):
    assert reg.entry_from(_event(tool_name="Bash")) is None


def _stdin(event):
    return json.dumps(event)


def test_us20_main_writes_entry_file_with_four_fields(reg, tmp_path):
    assert reg.main(_stdin(_event()), tmp_path) == 0
    written = json.loads((tmp_path / "agents" / "abc123.json").read_text())
    assert written == {"session": "sess-1", "run": "/runs/P/task", "step_id": "u5-write-1", "agent": "qa"}


def test_us20_main_garbage_stdin_writes_nothing(reg, tmp_path):
    assert reg.main("not json {", tmp_path) == 0
    assert not list(tmp_path.rglob("*.json"))


def test_us20_main_event_without_wf_step_writes_nothing(reg, tmp_path):
    event = _event(tool_input={"prompt": "Run folder: /runs/P/task", "subagent_type": "qa"})
    assert reg.main(_stdin(event), tmp_path) == 0
    assert not list(tmp_path.rglob("*.json"))


def test_us20_main_second_launch_keeps_first_entry(reg, tmp_path):
    reg.main(_stdin(_event()), tmp_path)
    other = "wf-step: u9-write-2\nRun folder: /runs/Q/other\n"
    assert reg.main(_stdin(_event(tool_input={"prompt": other, "subagent_type": "dev"})), tmp_path) == 0
    written = json.loads((tmp_path / "agents" / "abc123.json").read_text())
    assert written["step_id"] == "u5-write-1"
    assert written["agent"] == "qa"
