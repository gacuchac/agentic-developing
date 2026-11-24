"""Run a codex_review pass and fetch the source its quotes are checked against."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from scripts.workflow.review import saved_path

_CODEX_REVIEW = Path(__file__).resolve().parents[2] / "codex_review.py"


def run_pass(args: list[str], repo: Path) -> Path | None:
    """Run codex_review.py with args in repo; return the saved review path, or None."""
    proc = subprocess.run(
        [sys.executable, str(_CODEX_REVIEW), *args], cwd=repo, capture_output=True, text=True, check=False
    )
    return saved_path(proc.stderr)


def review_source(repo: Path, commit: str | None, base: str | None) -> str:
    """Return `git show --format=fuller <commit>` if commit is given, else `git diff <base>...HEAD`."""
    cmd = ["show", "--format=fuller", commit] if commit else ["diff", f"{base}...HEAD"]
    return subprocess.run(["git", *cmd], cwd=repo, capture_output=True, text=True, check=True).stdout
