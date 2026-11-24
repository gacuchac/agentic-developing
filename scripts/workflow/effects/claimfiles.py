from __future__ import annotations

import json
import os
from pathlib import Path


def create(active: Path, name: str, claim: dict) -> bool:
    """Create `active/name` atomically holding `claim`; False when it already exists."""
    active.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(active / name, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    with os.fdopen(fd, "w") as handle:
        json.dump(claim, handle)
    return True


def read(active: Path, name: str) -> dict | None:
    """Return the claim in `active/name`, or None when missing or not valid JSON."""
    try:
        return json.loads((active / name).read_text())
    except (OSError, ValueError):
        return None


def remove(active: Path, name: str) -> None:
    """Delete `active/name`; a missing file is fine."""
    (active / name).unlink(missing_ok=True)


def owned_by(active: Path, session: str) -> list[str]:
    """Return the names of the claim files in `active` whose session is `session`."""
    names = (p.name for p in active.iterdir()) if active.is_dir() else ()
    return [n for n in names if (read(active, n) or {}).get("session") == session]
