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
