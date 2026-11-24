"""PreToolUse hook: keep a session's file edits inside its own task."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKSPACE / "scripts" / "workflow"))

from effects import claimfiles  # noqa: E402

EDIT_TOOLS = {"Edit": "file_path", "Write": "file_path", "NotebookEdit": "notebook_path"}


def _inside(path: str, folder: str) -> bool:
    """Return True when `path` is `folder` or lies below it."""
    return Path(os.path.normpath(path)).is_relative_to(os.path.normpath(folder))


def _in_claim(path: str, claim: dict, workspace: str) -> bool:
    """Return True when `path` lies in the claim's run folder or in its checkout (unless that is the workspace)."""
    in_checkout = claim["checkout"] != workspace and _inside(path, claim["checkout"])
    return in_checkout or _inside(path, claim["run"])


def path_allowed(
    path: str, claim: dict | None, is_root_task: bool, others: list[dict], workspace: str
) -> tuple[bool, str]:
    """Return (allowed, reason) for an edit of `path` by the session holding `claim`.

    Without a claim, or outside `workspace`, the edit is allowed. Another claim's checkout or run
    folder is denied. The session's own folders are allowed; any other workspace path only for a root task."""
    if claim is None:
        return True, ""
    if any(_in_claim(path, other, workspace) for other in others):
        return False, f"{path} belongs to another task; edit only inside {claim['checkout']}."
    if _in_claim(path, claim, workspace) or not _inside(path, workspace) or is_root_task:
        return True, ""
    return False, f"{path} is outside your task; edit only inside {claim['checkout']}."


def _verdict(path: str, own: list[dict], others: list[dict], workspace: Path) -> tuple[bool, str]:
    """Return (allowed, reason) for `path`: allowed when `path_allowed` allows it for any claim in `own`."""
    if not own:
        return True, ""
    results = [
        path_allowed(path, c, os.path.normpath(c["checkout"]) == str(workspace), others, str(workspace)) for c in own
    ]
    return next((r for r in results if r[0]), results[0])


def _decide(event: dict, active: Path, workspace: Path) -> tuple[bool, str]:
    """Return (allowed, reason) for the Edit, Write or NotebookEdit call in `event`."""
    key = EDIT_TOOLS.get(event.get("tool_name"))
    if key is None:
        return True, ""
    claims = [c for p in active.glob("*.json") if (c := claimfiles.read(active, p.name))]
    mine = [c for c in claims if c.get("session") == event.get("session_id")]
    entry = claimfiles.read(active / "agents", f"{event.get('agent_id')}.json")
    own = [c for c in mine if entry and c["run"] == entry["run"]]
    if own:
        return _verdict(event["tool_input"][key], own, [c for c in claims if c not in own], workspace)
    return _verdict(event["tool_input"][key], mine, [c for c in claims if c not in mine], workspace)


def main(stdin: str, active: Path, workspace: Path) -> int:
    """Return 2 and print the reason to stderr when the JSON event in `stdin` edits outside its task, else 0.

    Unreadable input allows."""
    try:
        allowed, reason = _decide(json.loads(stdin), active, workspace)
    except Exception:
        return 0
    if not allowed:
        print(reason, file=sys.stderr)
    return 0 if allowed else 2


if __name__ == "__main__":
    sys.exit(main(sys.stdin.read(), WORKSPACE / ".claude" / "runs" / ".active", WORKSPACE))
