"""Git operations: commit, file at a commit, uncommitted diff."""
from __future__ import annotations

import subprocess
from pathlib import Path


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True).stdout


def commit(repo: Path, message: str, paths: list[str] | None = None) -> str:
    """Stage `paths` (all when None), commit only those, return the HEAD sha; RuntimeError(stderr) if git refuses."""
    only = ["--", *paths] if paths else []
    try:
        _git(repo, "add", "-A", *only)
        _git(repo, "commit", "-m", message, *only)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(e.stderr) from e
    return _git(repo, "rev-parse", "HEAD").strip()


def file_at(repo: Path, path: str, sha: str | None) -> str | None:
    """Return the file's text at `sha`, or in the working tree when sha is None; None when missing."""
    try:
        return (repo / path).read_text() if sha is None else _git(repo, "show", f"{sha}:{path}")
    except (OSError, subprocess.CalledProcessError):
        return None

