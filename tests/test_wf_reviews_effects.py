"""Tests for effects.reviews (US-8): run a pass and fetch the text to check quotes against."""

import contextlib
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


_STUB = (
    "import sys, time\n"
    "time.sleep(0.3)\n"
    "if sys.argv[1:2] == ['say']:\n"
    "    print('saved: ' + sys.argv[2], file=sys.stderr)\n"
)


@pytest.fixture
def stub(tmp_path: Path) -> Path:
    path = tmp_path / "stub_review.py"
    path.write_text(_STUB)
    return path


def _alive(pid: int) -> bool:
    import os

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def test_us8_collect_pass_returns_the_saved_path(tmp_path, stub):
    handle = reviews.start_pass(["say", "/x/saved-review.md"], tmp_path, tmp_path / "log.txt", script=stub)
    assert reviews.collect_pass(handle, 10) == Path("/x/saved-review.md")


def test_us8_collect_pass_without_saved_line_returns_none(tmp_path, stub):
    handle = reviews.start_pass(["silent"], tmp_path, tmp_path / "log.txt", script=stub)
    assert reviews.collect_pass(handle, 10) is None


def test_us8_collect_pass_timeout_returns_none_and_leaves_process_running(tmp_path, stub):
    import os
    import signal

    handle = reviews.start_pass(["say", "/x/r.md"], tmp_path, tmp_path / "log.txt", script=stub)
    try:
        assert reviews.collect_pass(handle, 0.05) is None
        assert _alive(handle["pid"])
    finally:
        with contextlib.suppress(ProcessLookupError):
            os.kill(handle["pid"], signal.SIGKILL)


def test_us8_start_pass_returns_promptly_with_pid_and_log(tmp_path, stub):
    import time

    log = tmp_path / "log.txt"
    t0 = time.monotonic()
    handle = reviews.start_pass(["say", "/x/r.md"], tmp_path, log, script=stub)
    elapsed = time.monotonic() - t0
    try:
        assert elapsed < 0.25
        assert isinstance(handle["pid"], int)
        assert handle["log"] == str(log)
    finally:
        reviews.collect_pass(handle, 10)
