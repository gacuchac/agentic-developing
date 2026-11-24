"""Pre-commit review gate (pure helpers only).

No new commit on a task branch until the previous one has a saved review.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]


def task_id(branch: str) -> str | None:
    """Return the part of `branch` after feature/, bugfix/ or hotfix/, else None."""
    for prefix in ("feature/", "bugfix/", "hotfix/"):
        if branch.startswith(prefix):
            return branch[len(prefix) :]
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
    """Return True when `folder` holds a saved review or evidence record for `sha`.

    A review-commit-*.md or review-tests-*.md counts when it names `sha` as its base and records `exit: 0`;
    an evidence-<sha>*.json counts when evidence_record.complete accepts it. A missing folder gives False.
    """
    needles = (f"base: commit {sha} ", "exit: 0 ")
    saved = [*folder.glob("review-commit-*.md"), *folder.glob("review-tests-*.md")]
    return any(all(n in f.read_text() for n in needles) for f in saved) or any(
        _complete_record(f) for f in folder.glob(f"evidence-{sha}*.json")
    )


def _complete_record(path: Path) -> bool:
    spec = importlib.util.spec_from_file_location("evidence_record", Path(__file__).with_name("evidence_record.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        return module.complete(json.loads(path.read_text()))
    except json.JSONDecodeError:
        return False


def nothing_to_review(repo: Path) -> bool:
    """Return True when every change in HEAD is a deletion or under .claude/skills/."""
    lines = subprocess.run(
        ["git", "show", "--name-status", "--format=", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.splitlines()
    return all(ln.startswith("D") or ln.split("\t")[-1].startswith(".claude/skills/") for ln in lines)


def needs_review(repo: Path) -> bool:
    """Return True when HEAD is not on dev and has exactly one parent.

    A merge commit needs no review. Depends only on `repo`.
    """
    on_dev = subprocess.run(
        ["git", "merge-base", "--is-ancestor", "HEAD", "dev"], cwd=repo, capture_output=True, check=False
    )
    off_dev = on_dev.returncode != 0
    parents = subprocess.run(
        ["git", "rev-list", "--parents", "-n", "1", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout
    return off_dev and len(parents.split()) == 2


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout.strip()


def main(workspace: Path = WORKSPACE) -> int:
    """Return 1 and print a blocking message when HEAD of the current task branch has no saved review, else 0.

    A repo with no commits returns 0.
    """
    if subprocess.run(["git", "rev-parse", "--verify", "-q", "HEAD"], capture_output=True, check=False).returncode:
        return 0
    branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    task = task_id(branch)
    if task is None or not needs_review(Path.cwd()) or nothing_to_review(Path.cwd()):
        return 0
    folder = run_folder(Path(_git("rev-parse", "--path-format=absolute", "--git-common-dir")), task, workspace)
    short = _git("rev-parse", "--short", "HEAD")
    if folder is None or any(reviewed(folder, sha) for sha in (_git("rev-parse", "HEAD"), short)):
        return 0
    print(
        f"Commit blocked: HEAD {short} on {branch} has no saved review in {folder}. "
        f"Unblock it with a saved commit review "
        f"(python3 ~/Developing/scripts/codex_review.py commit --commit {short} ...), a saved tests review, "
        "or an evidence record (python3 scripts/hooks/evidence_record.py write --run <run folder>).",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
