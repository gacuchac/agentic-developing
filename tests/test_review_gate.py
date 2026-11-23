import importlib.util
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
