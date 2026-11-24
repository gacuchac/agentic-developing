"""Git operations: commit, file at a commit, uncommitted diff."""
from __future__ import annotations

import subprocess
from pathlib import Path


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True).stdout


def commit(repo: Path, message: str, paths: list[str] | None = None) -> str:
    """Stage `paths` (all when None), commit only those, return the HEAD sha; RuntimeError(stderr) if git refuses."""
    only = [] if paths is None else ["--", *paths]
    try:
        _git(repo, "add", *(["-A"] if paths is None else only))
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



def worktree_diff(repo: Path) -> str:
    """Return `git diff HEAD` plus each untracked file as a new-file section; the index is untouched."""
    out = _git(repo, "diff", "HEAD")
    for p in _git(repo, "ls-files", "--others", "--exclude-standard").splitlines():
        out += f"--- /dev/null\n+++ b/{p}\n+" + "\n+".join((repo / p).read_text().splitlines()) + "\n"
    return out


def launch_info(repo: Path) -> tuple[str, str]:
    """Return (current branch, merge-base of HEAD and dev); RuntimeError when there is no dev or HEAD is detached."""
    try:
        branch = _git(repo, "rev-parse", "--abbrev-ref", "HEAD").strip()
        launch = _git(repo, "merge-base", "HEAD", "dev").strip()
    except subprocess.CalledProcessError as e:
        raise RuntimeError(e.stderr) from e
    if branch == "HEAD":
        raise RuntimeError("HEAD is detached")
    return branch, launch
