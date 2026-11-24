"""Run a codex_review pass and fetch the source its quotes are checked against."""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

from scripts.workflow.review import saved_path

_CODEX_REVIEW = Path(__file__).resolve().parents[2] / "codex_review.py"


def run_pass(args: list[str], repo: Path) -> Path | None:
    """Run codex_review.py with args in repo; return the saved review path, or None."""
    proc = subprocess.run(
        [sys.executable, str(_CODEX_REVIEW), *args], cwd=repo, capture_output=True, text=True, check=False
    )
    return saved_path(proc.stderr)


def start_pass(args: list[str], repo: Path, log: Path, script: Path | None = None) -> dict:
    """Start codex_review.py (or script) with args detached in repo, stderr appended to log; return {"pid", "log"}."""
    with log.open("a") as err:
        proc = subprocess.Popen(
            [sys.executable, str(script or _CODEX_REVIEW), *args], cwd=repo, stdout=subprocess.DEVNULL,
            stderr=err, start_new_session=True,
        )
    return {"pid": proc.pid, "log": str(log)}


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return os.waitpid(pid, os.WNOHANG)[0] == 0
    except ProcessLookupError:
        return False
    except ChildProcessError:
        return True


def collect_pass(handle: dict, timeout: float) -> Path | None:
    """Wait up to timeout seconds for the pass to exit, never killing it; return its saved review path or None."""
    deadline = time.monotonic() + timeout
    while _alive(handle["pid"]) and time.monotonic() < deadline:
        time.sleep(0.02)
    return saved_path(Path(handle["log"]).read_text())


def review_source(repo: Path, commit: str | None, base: str | None) -> str:
    """Return `git show --format=fuller <commit>` if commit is given, else `git diff <base>...HEAD`."""
    cmd = ["show", "--format=fuller", commit] if commit else ["diff", f"{base}...HEAD"]
    return subprocess.run(["git", *cmd], cwd=repo, capture_output=True, text=True, check=True).stdout
