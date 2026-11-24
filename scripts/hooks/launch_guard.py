"""PreToolUse hook: allow workflow agents only at their step, and `wf release` only from the main session."""

from __future__ import annotations

import re

WORKFLOW_AGENTS = ("qa", "implementer")


def _step_id(prompt: str) -> str | None:
    """Return the id on the `wf-step: <id>` line of `prompt`, or None."""
    match = re.search(r"^wf-step:\s*(\S+)", prompt, re.MULTILINE)
    return match.group(1) if match else None


def _decide_agent(tool_input: dict, state: dict | None) -> tuple[bool, str]:
    """Decide an Agent launch against the pending step in `state`."""
    agent = tool_input.get("subagent_type")
    pending = (state or {}).get("pending") or {}
    if agent not in WORKFLOW_AGENTS or pending.get("kind") != "agent":
        return True, ""
    if _step_id(tool_input.get("prompt", "")) == pending.get("step_id") and agent == pending.get("agent"):
        return True, ""
    return False, f"Pending step is {pending.get('step_id')} for agent {pending.get('agent')}; use its `wf-step:` line."
