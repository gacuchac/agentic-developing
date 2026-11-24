"""Tests for gitops.launch_info (US-11)."""

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from workflow.effects import gitops  # noqa: E402


def _g(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()


def _repo(tmp_path, with_dev=True):
    repo = tmp_path / "r"
    repo.mkdir()
    _g(repo, "init", "-q", "-b", "main")
    _g(repo, "config", "user.email", "t@t")
    _g(repo, "config", "user.name", "t")
    (repo / "a.txt").write_text("a")
    _g(repo, "add", "-A")
    _g(repo, "commit", "-qm", "one")
    if with_dev:
        _g(repo, "branch", "dev")
    return repo


def test_us11_launch_info_returns_branch_and_merge_base(tmp_path):
    repo = _repo(tmp_path)
    base = _g(repo, "rev-parse", "dev")
    _g(repo, "checkout", "-q", "-b", "feature/x")
    (repo / "b.txt").write_text("b")
    _g(repo, "add", "-A")
    _g(repo, "commit", "-qm", "two")
    assert gitops.launch_info(repo) == ("feature/x", base)


def test_us11_launch_info_raises_without_dev(tmp_path):
    repo = _repo(tmp_path, with_dev=False)
    _g(repo, "checkout", "-q", "-b", "feature/x")
    with pytest.raises(RuntimeError):
        gitops.launch_info(repo)


def test_us11_launch_info_raises_on_detached_head(tmp_path):
    repo = _repo(tmp_path)
    _g(repo, "checkout", "-q", "--detach")
    with pytest.raises(RuntimeError):
        gitops.launch_info(repo)
