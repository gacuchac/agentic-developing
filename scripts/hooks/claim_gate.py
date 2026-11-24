"""Pre-commit claim gate: refuse a commit on a branch another session holds."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]


def blocked(branch: str, session: str, claims: list[dict]) -> str | None:
    """Return a message naming the holder when a claim has `branch` and a different `session`, else None.

    An empty `session` is never blocked.
    """
    if not session:
        return None
    for claim in claims:
        if claim["branch"] == branch and claim["session"] != session:
            return (
                f"Commit blocked: branch {branch} is held by session {claim['session']} (checkout {claim['checkout']})."
            )
    return None


def _load_claims(workspace: Path) -> list[dict]:
    return [json.loads(f.read_text()) for f in sorted((workspace / ".claude" / "runs" / ".active").glob("*.json"))]


def main(workspace: Path = WORKSPACE) -> int:
    """Return 1 and print the blocking message when another session holds the current branch, else 0."""
    branch = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    message = blocked(branch, os.environ.get("CLAUDE_CODE_SESSION_ID", ""), _load_claims(workspace))
    if message is None:
        return 0
    print(message, file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
