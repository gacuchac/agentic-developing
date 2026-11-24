"""Agent registry entries (pure helpers only).

Turns a subagent launch event into the entry that names the agent's task.
"""

from __future__ import annotations

import re

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
