"""Tests for the root checkout warning in wf status (US-15)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import state as st
import wf


def _g(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True)


def _workspace(tmp_path: Path, branch: str) -> Path:
    ws = tmp_path / "Developing"
    ws.mkdir()
    _g(ws, "init", "-q", "-b", branch)
    _g(ws, "config", "user.email", "t@t")
    _g(ws, "config", "user.name", "t")
    (ws / "a.txt").write_text("a")
    _g(ws, "add", "-A")
    _g(ws, "commit", "-qm", "one")
    return ws


def _run(ws: Path, project: str) -> Path:
    run = ws / ".claude" / "runs" / project / "t1"
    run.mkdir(parents=True)
    st.save(run, st.new_state("t1", "b", "l"))
    return run


def test_us15_root_warning_project_task_root_off_dev():
    message = wf.root_warning("feature/x", False)
    assert message is not None
    assert "\n" not in message
    assert "root" in message.lower()
    assert "dev" in message


@pytest.mark.parametrize("branch", ["main", "feature/x", ""])
def test_us15_root_warning_any_non_dev_branch_warns(branch):
    assert wf.root_warning(branch, False) is not None


def test_us15_root_warning_none_when_root_on_dev():
    assert wf.root_warning("dev", False) is None


@pytest.mark.parametrize("branch", ["dev", "feature/x"])
def test_us15_root_warning_none_for_root_task(branch):
    assert wf.root_warning(branch, True) is None


def test_us15_status_warns_when_root_moved_off_dev(tmp_path, capsys):
    ws = _workspace(tmp_path, "feature/x")
    run = _run(ws, "proj")
    assert wf.main(["status", str(run)]) == 0
    lines = capsys.readouterr().out.rstrip("\n").split("\n")
    assert not lines[-1].startswith("held by:")
    assert "root" in lines[-1].lower()
    assert "dev" in lines[-1]
