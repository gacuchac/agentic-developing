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


def _decide(event: dict, active: Path, workspace: Path) -> tuple[bool, str]:
    """Return (allowed, reason) for the Edit, Write or NotebookEdit call in `event`."""
    key = EDIT_TOOLS.get(event.get("tool_name"))
    if key is None:
        return True, ""
    names = claimfiles.owned_by(active, event.get("session_id"))
    claim = claimfiles.read(active, names[0]) if names else None
    others = [c for p in active.glob("*.json") if (c := claimfiles.read(active, p.name)) and c != claim]
    is_root = claim is not None and os.path.normpath(claim["checkout"]) == str(workspace)
    return path_allowed(event["tool_input"][key], claim, is_root, others, str(workspace))


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
