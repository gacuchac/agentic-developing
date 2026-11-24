import importlib.util
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
