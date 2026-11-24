"""Tests for the user-only `wf release <run> --reason <text>` command (US-13)."""

from __future__ import annotations

import os

import claims
import pytest
import wf
from effects import procs

NAME = "proj--t1.json"


@pytest.fixture
def held(tmp_path, monkeypatch):
    monkeypatch.delenv("WF_AGENT", raising=False)
    run = tmp_path / "Developing" / ".claude" / "runs" / "proj" / "t1"
    run.mkdir(parents=True)
    active = run.parents[1] / ".active"
    pid = os.getpid()
    claim = claims.make_claim("old-session", pid, procs.pid_start(pid) or "", str(run), "c", "feature/x", "2026-01-01T00:00:00")
    assert claims.acquire(active, NAME, claim, procs.pid_alive, procs.pid_start, lambda _m: None)[0] == "created"
    return run, active


def test_us13_release_removes_claim(held):
    run, active = held
    assert wf.main(["release", str(run), "--reason", "session crashed"]) == 0
    assert not (active / NAME).exists()


def test_us13_release_logs_reason_and_old_holder(held):
    run, _ = held
    assert wf.main(["release", str(run), "--reason", "session crashed"]) == 0
    rows = [r for r in (run / "decisions.tsv").read_text().splitlines() if "release" in r]
    assert len(rows) == 1
    assert "session crashed" in rows[0]
    assert "old-session" in rows[0]


def test_us13_release_without_reason_exits_2_and_keeps_claim(held, capsys):
    run, active = held
    with pytest.raises(SystemExit) as exc:
        wf.main(["release", str(run)])
    assert exc.value.code == 2
    assert "--reason" in capsys.readouterr().err
    assert (active / NAME).exists()


def test_us13_release_refused_for_workflow_agent(held, monkeypatch):
    run, active = held
    monkeypatch.setenv("WF_AGENT", "1")
    assert wf.main(["release", str(run), "--reason", "take over"]) != 0
    assert (active / NAME).exists()
    log = run / "decisions.tsv"
    assert not log.exists() or "take over" not in log.read_text()
