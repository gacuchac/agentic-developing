"""PreToolUse hook: allow workflow agents only at their step, and `wf release` only from the main session."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKSPACE / "scripts" / "workflow"))

from effects import claimfiles  # noqa: E402

WORKFLOW_AGENTS = ("qa", "implementer")
RELEASE = re.compile(r"\bwf(\.py)?\s+release\b")


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


def decide(event: dict, claim: dict | None, state: dict | None) -> tuple[bool, str]:
    """Return (allowed, reason) for the tool call in `event`.

    A qa or implementer launch must carry the pending step's `wf-step:` id and agent when
    the session's `claim` has a pending agent step in `state`; `wf release` from a subagent is denied."""
    tool, tool_input = event.get("tool_name"), event.get("tool_input") or {}
    if tool == "Bash" and "agent_id" in event and RELEASE.search(tool_input.get("command", "")):
        return False, "wf release is for the user, not a subagent."
    if tool != "Agent" or claim is None:
        return True, ""
    return _decide_agent(tool_input, state)


def _load_state(claim: dict) -> dict | None:
    """Return the state.json of the claim's run folder, or None when unreadable."""
    try:
        return json.loads((Path(claim["run"]) / "state.json").read_text())
    except (OSError, ValueError, KeyError):
        return None


def main(stdin: str, active: Path) -> int:
    """Return 2 and print the reason to stderr when the JSON event in `stdin` is denied, else 0.

    Looks up the session's claim in `active`; unreadable input or state allows."""
    try:
        event = json.loads(stdin)
        names = claimfiles.owned_by(active, event.get("session_id"))
        claim = claimfiles.read(active, names[0]) if names else None
        allowed, reason = decide(event, claim, _load_state(claim) if claim else None)
    except Exception:
        return 0
    if not allowed:
        print(reason, file=sys.stderr)
    return 0 if allowed else 2


if __name__ == "__main__":
    sys.exit(main(sys.stdin.read(), WORKSPACE / ".claude" / "runs" / ".active"))
