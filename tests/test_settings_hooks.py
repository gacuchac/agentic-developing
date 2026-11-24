from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SETTINGS = ROOT / ".claude" / "settings.json"


def _entries(event: str, matcher: str | None) -> list[dict]:
    hooks = json.loads(SETTINGS.read_text())["hooks"].get(event, [])
    return [h for e in hooks if e.get("matcher") == matcher for h in e["hooks"]]


def _command(name: str) -> str:
    return f'python3 "${{CLAUDE_PROJECT_DIR}}"/scripts/hooks/{name}.py'


def _assert_wired(event: str, matcher: str | None, name: str) -> dict:
    found = [h for h in _entries(event, matcher) if h.get("command") == _command(name)]
    assert found, f"{event}/{matcher} does not run {name}.py"
    assert found[0]["type"] == "command"
    assert (ROOT / "scripts" / "hooks" / f"{name}.py").is_file()
    return found[0]


def test_us14_pretooluse_agent_bash_runs_launch_guard() -> None:
    _assert_wired("PreToolUse", "Agent|Bash", "launch_guard")


def test_us14_pretooluse_edit_write_notebook_runs_edit_guard() -> None:
    _assert_wired("PreToolUse", "Edit|Write|NotebookEdit", "edit_guard")


def test_us14_subagent_stop_runs_subagent_record() -> None:
    hooks = json.loads(SETTINGS.read_text())["hooks"].get("SubagentStop", [])
    commands = [h["command"] for e in hooks for h in e["hooks"]]
    assert _command("subagent_record") in commands


def test_us14_handback_report_runs_subagent_record() -> None:
    hooks = json.loads(SETTINGS.read_text())["hooks"]
    commands = [
        h["command"]
        for event in ("PreToolUse", "PostToolUse")
        for e in hooks.get(event, [])
        if e.get("matcher") == "SubagentHandback"
        for h in e["hooks"]
    ]
    assert _command("subagent_record") in commands


def test_us14_session_end_runs_session_end_with_5s_timeout() -> None:
    hooks = json.loads(SETTINGS.read_text())["hooks"].get("SessionEnd", [])
    found = [h for e in hooks for h in e["hooks"] if h.get("command") == _command("session_end")]
    assert found, "SessionEnd does not run session_end.py"
    assert found[0]["type"] == "command"
    assert found[0]["timeout"] == 5


def test_us20_posttooluse_agent_runs_agent_registry_with_10s_timeout() -> None:
    assert _entries("PostToolUse", "Agent") == [
        {"type": "command", "command": _command("agent_registry"), "timeout": 10}
    ]
    assert _entries("PostToolUse", "Edit|Write") == [
        {"type": "command", "command": _command("post_edit"), "timeout": 30}
    ]
