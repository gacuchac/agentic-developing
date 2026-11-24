"""Tests for session identity and the claim check in wf commands (US-13)."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import claims
import pytest
import wf
from effects import procs

PLAN = "# Plan\n\n### 1. First thing (US-1)\nLane: fast\nDo the first.\n"
NAME = "proj--t1.json"


def _g(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True)


@pytest.fixture
def env(tmp_path, monkeypatch):
    for key in ("CLAUDE_CODE_SESSION_ID", "CLAUDE_PID"):
        monkeypatch.delenv(key, raising=False)
    repo = tmp_path / "Developing" / "proj"
    repo.mkdir(parents=True)
    _g(repo, "init", "-q", "-b", "main")
    _g(repo, "config", "user.email", "t@t")
    _g(repo, "config", "user.name", "t")
    (repo / "a.txt").write_text("a")
    _g(repo, "add", "-A")
    _g(repo, "commit", "-qm", "one")
    _g(repo, "branch", "dev")
    _g(repo, "checkout", "-q", "-b", "feature/x")
    run = tmp_path / "Developing" / ".claude" / "runs" / "proj" / "t1"
    run.mkdir(parents=True)
    (run / "plan.md").write_text(PLAN)
    return run, run.parents[1] / ".active"


def _session(session: str) -> dict:
    return {"CLAUDE_CODE_SESSION_ID": session, "CLAUDE_PID": str(os.getpid())}


def _hold(active: Path, session: str) -> None:
    pid = os.getpid()
    claim = claims.make_claim(session, pid, procs.pid_start(pid) or "", "r", "c", "feature/other", "2026-01-01T00:00:00")
    assert claims.acquire(active, NAME, claim, procs.pid_alive, procs.pid_start, lambda _m: None)[0] == "created"


def test_us13_identity_reads_session_and_pid():
    assert wf.identity({"CLAUDE_CODE_SESSION_ID": "s1", "CLAUDE_PID": "4242"}) == ("s1", 4242)


@pytest.mark.parametrize("mapping", [{}, {"CLAUDE_CODE_SESSION_ID": "s1"}, {"CLAUDE_PID": "4242"}])
def test_us13_identity_empty_when_either_missing(mapping):
    assert wf.identity(mapping) == ("", 0)


def test_us13_run_claim_creates_claim_for_session(env):
    run, active = env
    assert wf.run_claim(run, _session("s1"), wf.default_ctx(run)) == []
    held = json.loads((active / NAME).read_text())
    assert held["session"] == "s1"
    assert held["branch"] == "feature/x"
    assert held["pid"] == os.getpid()


def test_us13_run_claim_refuses_live_holder_naming_it(env):
    run, active = env
    _hold(active, "other-session")
    errors = wf.run_claim(run, _session("s2"), wf.default_ctx(run))
    assert len(errors) == 1
    assert "other-session" in errors[0]
    assert "feature/other" in errors[0]
    assert "2026-01-01T00:00:00" in errors[0]
    assert json.loads((active / NAME).read_text())["session"] == "other-session"


def test_us13_run_claim_own_session_is_not_refused(env):
    run, active = env
    _hold(active, "s1")
    assert wf.run_claim(run, _session("s1"), wf.default_ctx(run)) == []


def test_us13_empty_identity_creates_no_claim(env):
    run, active = env
    assert wf.run_claim(run, {}, wf.default_ctx(run)) == []
    assert not (active / NAME).exists()


def test_us13_empty_identity_does_not_refuse_held_task(env):
    run, active = env
    _hold(active, "other-session")
    assert wf.run_claim(run, {}, wf.default_ctx(run)) == []


def test_us13_take_on_held_task_refused_state_unchanged(env, monkeypatch, capsys):
    run, active = env
    assert wf.main(["start", str(run), "--plan", "plan.md"]) == 0
    before = (run / "state.json").read_bytes()
    _hold(active, "other-session")
    for key, value in _session("s2").items():
        monkeypatch.setenv(key, value)
    code = wf.main(["take", str(run), "anything"])
    assert code == 2
    assert "other-session" in capsys.readouterr().err
    assert (run / "state.json").read_bytes() == before


def test_us13_start_on_held_task_refused_no_state(env, monkeypatch):
    run, active = env
    _hold(active, "other-session")
    for key, value in _session("s2").items():
        monkeypatch.setenv(key, value)
    assert wf.main(["start", str(run), "--plan", "plan.md"]) == 2
    assert not (run / "state.json").exists()


def test_us13_status_of_held_task_runs_and_names_holder(env, monkeypatch, capsys):
    run, active = env
    assert wf.main(["start", str(run), "--plan", "plan.md"]) == 0
    capsys.readouterr()
    _hold(active, "other-session")
    for key, value in _session("s2").items():
        monkeypatch.setenv(key, value)
    assert wf.main(["status", str(run)]) == 0
    assert "other-session" in capsys.readouterr().out
