"""Pre-commit review gate: no new commit on a task branch until the previous one has a saved review (pure helpers only)."""
from __future__ import annotations

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
