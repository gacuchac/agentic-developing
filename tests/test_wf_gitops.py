"""Tests for effects.gitops (US-9)."""

import subprocess
from pathlib import Path

import pytest
from effects import gitops


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _write(repo: Path, rel: str, text: str) -> None:
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    _write(tmp_path, "src/a.py", "a = 1\n")
    _write(tmp_path, "tests/t.py", "t = 1\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "init")
    return tmp_path


def test_us9_commit_with_paths_leaves_other_changes_uncommitted(repo: Path) -> None:
    _write(repo, "src/a.py", "a = 2\n")
    _write(repo, "tests/t.py", "t = 2\n")
    gitops.commit(repo, "only test", ["tests/t.py"])
    status = _git(repo, "status", "--porcelain")
    assert "src/a.py" in status
    assert "tests/t.py" not in status


def test_us9_commit_none_commits_everything_and_returns_head_sha(repo: Path) -> None:
    _write(repo, "src/a.py", "a = 2\n")
    _write(repo, "new.py", "n = 1\n")
    sha = gitops.commit(repo, "all", None)
    assert _git(repo, "status", "--porcelain").strip() == ""
    assert sha == _git(repo, "rev-parse", "HEAD").strip()


def test_us9_commit_raises_runtime_error_when_hook_fails(repo: Path) -> None:
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\necho nope >&2\nexit 1\n")
    hook.chmod(0o755)
    _write(repo, "src/a.py", "a = 2\n")
    with pytest.raises(RuntimeError):
        gitops.commit(repo, "x", None)


def test_us9_file_at_reads_old_version_at_sha(repo: Path) -> None:
    old = _git(repo, "rev-parse", "HEAD").strip()
    _write(repo, "src/a.py", "a = 2\n")
    gitops.commit(repo, "change", None)
    assert gitops.file_at(repo, "src/a.py", old) == "a = 1\n"


def test_us9_file_at_none_sha_reads_working_tree(repo: Path) -> None:
    _write(repo, "src/a.py", "a = 99\n")
    assert gitops.file_at(repo, "src/a.py", None) == "a = 99\n"


def test_us9_file_at_missing_path_returns_none(repo: Path) -> None:
    sha = _git(repo, "rev-parse", "HEAD").strip()
    assert gitops.file_at(repo, "nope.py", sha) is None
    assert gitops.file_at(repo, "nope.py", None) is None


def test_us9_worktree_diff_shows_edit_as_minus_plus(repo: Path) -> None:
    _write(repo, "src/a.py", "a = 2\n")
    diff = gitops.worktree_diff(repo)
    assert "-a = 1" in diff
    assert "+a = 2" in diff


def test_us9_worktree_diff_shows_untracked_file_as_new(repo: Path) -> None:
    _write(repo, "new.py", "x = 1\ny = 2\n")
    diff = gitops.worktree_diff(repo)
    assert "--- /dev/null" in diff
    assert "+++ b/new.py" in diff
    assert "+x = 1" in diff
    assert "+y = 2" in diff


def test_us9_worktree_diff_omits_committed_changes(repo: Path) -> None:
    _write(repo, "src/a.py", "a = 2\n")
    gitops.commit(repo, "c", None)
    assert gitops.worktree_diff(repo).strip() == ""


def test_us9_worktree_diff_leaves_index_untouched(repo: Path) -> None:
    _write(repo, "src/a.py", "a = 2\n")
    _write(repo, "new.py", "n = 1\n")
    before = _git(repo, "status", "--porcelain")
    gitops.worktree_diff(repo)
    assert _git(repo, "status", "--porcelain") == before
