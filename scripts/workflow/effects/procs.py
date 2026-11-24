"""Process liveness and start time."""

from __future__ import annotations

import os
import subprocess


def pid_alive(pid: int) -> bool:
    """True when a process with this pid exists (permission-denied counts as alive)."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def pid_start(pid: int) -> str | None:
    """Return the process start time from `ps -o lstart=`, stripped; None when the process doesn't exist."""
    out = subprocess.run(["ps", "-o", "lstart=", "-p", str(pid)], capture_output=True, text=True, check=False)
    return out.stdout.strip() or None
