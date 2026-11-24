"""PostToolUse hook: register a launched workflow agent under `.active/agents/`."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKSPACE / "scripts" / "workflow"))

from effects import claimfiles  # noqa: E402

_STEP = re.compile(r"^wf-step:\s*(\S+)\s*$", re.MULTILINE)
_RUN = re.compile(r"^Run folder:\s*(.+?)\s*$", re.MULTILINE)


def entry_from(event: dict) -> tuple[str, dict] | None:
    """Return (`<agentId>.json`, entry) for an Agent launch event, else None.

    The entry holds session, run folder, step id and agent type. None is returned
    when the tool is not Agent or the response or prompt lacks an id, wf-step or Run folder line."""
    if event.get("tool_name") != "Agent":
        return None
    agent_id = (event.get("tool_response") or {}).get("agentId")
    tool_input = event.get("tool_input") or {}
    prompt = tool_input.get("prompt", "")
    step, run = _STEP.search(prompt), _RUN.search(prompt)
    if not (agent_id and step and run):
        return None
    entry = {
        "session": event["session_id"],
        "run": run.group(1),
        "step_id": step.group(1),
        "agent": tool_input["subagent_type"],
    }
    return f"{agent_id}.json", entry


def main(stdin: str, active: Path) -> int:
    """Write the launch event's entry to `active/agents/<agentId>.json`, keeping an existing one; return 0 always.

    Unreadable input and events without an entry write nothing."""
    try:
        event = json.loads(stdin)
    except ValueError:
        return 0
    found = entry_from(event) if isinstance(event, dict) else None
    if found:
        claimfiles.create(active / "agents", *found)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.stdin.read(), WORKSPACE / ".claude" / "runs" / ".active"))
