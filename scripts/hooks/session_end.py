"""SessionEnd hook: remove the ending session's claims."""

from __future__ import annotations

import json
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKSPACE / "scripts" / "workflow"))

import claims  # noqa: E402


def main(stdin: str, active: Path) -> int:
    """Release the claims in `active` held by the `session_id` in the JSON `stdin`.

    Always returns 0; unreadable input or a missing folder releases nothing."""
    try:
        session = json.loads(stdin).get("session_id")
        if isinstance(session, str):
            claims.release_session(active, session)
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.stdin.read(), WORKSPACE / ".claude" / "runs" / ".active"))
