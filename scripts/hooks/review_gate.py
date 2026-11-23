"""Pre-commit review gate: no new commit on a task branch until the previous one has a saved review (pure helpers only)."""
from __future__ import annotations

import subprocess
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]


def task_id(branch: str) -> str | None:
    """Return the part of `branch` after feature/, bugfix/ or hotfix/, else None."""
    for prefix in ("feature/", "bugfix/", "hotfix/"):
        if branch.startswith(prefix):
            return branch[len(prefix):]
    return None


def run_folder(common_dir: Path, task: str, workspace: Path) -> Path | None:
    """Return workspace/.claude/runs/<project>/<task> for the repo owning `common_dir`.

    The project is workspace.name if the repo is the workspace, repo.name if the
    repo is a direct child of the workspace, else None is returned."""
    repo = common_dir.parent
    if repo == workspace:
        project = workspace.name
    elif repo.parent == workspace:
        project = repo.name
    else:
        return None
    return workspace / ".claude" / "runs" / project / task


def reviewed(folder: Path, sha: str) -> bool:
    """Return True when any folder/review-commit-*.md names `sha` as its base (any verdict); a missing folder gives False."""
    return any(f"base: commit {sha} " in f.read_text() for f in folder.glob("review-commit-*.md"))


def needs_review(repo: Path) -> bool:
    """Return True when HEAD is not on dev and has exactly one parent (a merge commit needs no review). Depends only on `repo`."""
    off_dev = subprocess.run(["git", "merge-base", "--is-ancestor", "HEAD", "dev"], cwd=repo, capture_output=True, check=False).returncode != 0
    parents = subprocess.run(["git", "rev-list", "--parents", "-n", "1", "HEAD"], cwd=repo, capture_output=True, text=True, check=True).stdout
    return off_dev and len(parents.split()) == 2
