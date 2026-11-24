"""PreToolUse hook: keep a session's file edits inside its own task."""

from __future__ import annotations

import os
from pathlib import Path


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
