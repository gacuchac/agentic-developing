"""Tests for effects.reviews (US-8): run a pass and fetch the text to check quotes against."""

import subprocess
from pathlib import Path

import pytest
from effects import reviews


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=repo, check=True, capture_output=True, text=True,
    ).stdout


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    (tmp_path / "a.txt").write_text("one\n")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "first")
    return tmp_path


def _commit_line(repo: Path, line: str, msg: str) -> str:
    with (repo / "a.txt").open("a") as f:
        f.write(line + "\n")
    _git(repo, "commit", "-qam", msg)
    return _git(repo, "rev-parse", "HEAD").strip()


def test_us8_run_pass_unknown_pass_returns_none(tmp_path):
    assert reviews.run_pass(["no-such-pass"], tmp_path) is None


def test_us8_review_source_commit_has_message_and_added_line(repo):
    sha = _commit_line(repo, "added-marker-line", "unique commit message")
    out = reviews.review_source(repo, sha, None)
    assert "unique commit message" in out
    assert "+added-marker-line" in out


def test_us8_review_source_base_returns_diff_to_head(repo):
    base = _git(repo, "rev-parse", "HEAD").strip()
    _commit_line(repo, "line-two", "second")
    _commit_line(repo, "line-three", "third")
    out = reviews.review_source(repo, None, base)
    assert "+line-two" in out
    assert "+line-three" in out
    assert "third" not in out.replace("line-three", "")
