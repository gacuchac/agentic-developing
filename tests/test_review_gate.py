import importlib.util
import subprocess
from pathlib import Path

import pytest

_path = Path(__file__).resolve().parents[1] / "scripts" / "hooks" / "review_gate.py"
_spec = importlib.util.spec_from_file_location("review_gate", _path)
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)

WS_NAMES = ["Developing", "other-ws"]


def _ws(tmp_path, name):
    return tmp_path / "deep" / name


def test_us2_task_id_strips_feature_and_hotfix_prefix():
    assert gate.task_id("feature/x") == "x"
    assert gate.task_id("hotfix/a-b") == "a-b"
    assert gate.task_id("bugfix/y") == "y"


def test_us2_task_id_is_none_for_non_task_branches():
    assert gate.task_id("dev") is None
    assert gate.task_id("feat/x") is None


@pytest.mark.parametrize("name", WS_NAMES)
def test_us2_run_folder_for_project(tmp_path, name):
    ws = _ws(tmp_path, name)
    got = gate.run_folder(ws / "proj" / ".git", "t", ws)
    assert got == ws / ".claude" / "runs" / "proj" / "t"


@pytest.mark.parametrize("name", WS_NAMES)
def test_us2_run_folder_for_workspace_itself(tmp_path, name):
    ws = _ws(tmp_path, name)
    got = gate.run_folder(ws / ".git", "t", ws)
    assert got == ws / ".claude" / "runs" / name / "t"


@pytest.mark.parametrize("name", WS_NAMES)
def test_us2_run_folder_for_worktree_same_common_dir_as_project(tmp_path, name):
    # A worktree's `git rev-parse --git-common-dir` is the main repo's .git,
    # so it is the same input as the project case.
    ws = _ws(tmp_path, name)
    assert gate.run_folder(ws / "proj" / ".git", "t", ws) == ws / ".claude" / "runs" / "proj" / "t"


@pytest.mark.parametrize("name", WS_NAMES)
def test_us2_run_folder_none_outside_workspace(tmp_path, name):
    ws = _ws(tmp_path, name)
    assert gate.run_folder(tmp_path / "elsewhere" / "repo" / ".git", "t", ws) is None


@pytest.mark.parametrize("name", WS_NAMES)
def test_us2_run_folder_none_for_nested_repo(tmp_path, name):
    ws = _ws(tmp_path, name)
    assert gate.run_folder(ws / "a" / "b" / ".git", "t", ws) is None


SHA = "a" * 40


def _header(pass_name, sha):
    return f"<!-- pass: {pass_name} | model: m | base: commit {sha} | exit: 0 | 2026-01-01 00:00:00 -->\nbody\n"


def test_us2_reviewed_true_for_commit_review_with_sha(tmp_path):
    (tmp_path / "review-commit-1.md").write_text(_header("commit", SHA))
    assert gate.reviewed(tmp_path, SHA) is True


def test_us2_reviewed_false_for_other_sha(tmp_path):
    (tmp_path / "review-commit-1.md").write_text(_header("commit", "b" * 40))
    assert gate.reviewed(tmp_path, SHA) is False


def test_us2_reviewed_false_for_sha_prefix_only(tmp_path):
    (tmp_path / "review-commit-1.md").write_text(_header("commit", SHA[:12]))
    assert gate.reviewed(tmp_path, SHA) is False


def test_us2_reviewed_false_for_principles_review(tmp_path):
    (tmp_path / "review-principles-1.md").write_text(_header("principles", SHA))
    assert gate.reviewed(tmp_path, SHA) is False


def test_us2_reviewed_false_for_empty_or_missing_folder(tmp_path):
    assert gate.reviewed(tmp_path, SHA) is False
    assert gate.reviewed(tmp_path / "missing", SHA) is False


def _git(*args):
    subprocess.run(["git", *args], check=True, capture_output=True)


def _commit(name):
    Path(name).write_text(name)
    _git("add", name)
    _git("commit", "-m", name)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _git("init", "-b", "dev")
    _git("config", "user.name", "t")
    _git("config", "user.email", "t@example.com")
    _git("config", "commit.gpgsign", "false")
    _commit("base")
    _git("checkout", "-b", "feature/x")
    return tmp_path


def test_us2_needs_review_false_right_after_branching(repo):
    assert gate.needs_review(repo) is False


def test_us2_needs_review_true_after_one_commit_on_branch(repo):
    _commit("own")
    assert gate.needs_review(repo) is True


def test_us2_needs_review_false_when_head_is_merge_of_dev(repo):
    _commit("own")
    _git("checkout", "dev")
    _commit("newdev")
    _git("checkout", "feature/x")
    _git("merge", "--no-ff", "-m", "merge dev", "dev")
    assert gate.needs_review(repo) is False


def test_us2_needs_review_true_when_repo_has_no_dev(repo):
    _git("branch", "-m", "dev", "main")
    _commit("own")
    assert gate.needs_review(repo) is True


def test_us2_needs_review_uses_repo_arg_not_cwd(repo, tmp_path_factory, monkeypatch):
    _commit("own")
    elsewhere = tmp_path_factory.mktemp("elsewhere")
    monkeypatch.chdir(elsewhere)
    assert gate.needs_review(repo) is True
