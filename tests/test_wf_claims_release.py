from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "workflow"))

import claims  # noqa: E402
from effects import claimfiles  # noqa: E402


def _claim(session: str) -> dict:
    return claims.make_claim(session, 1, "start", "run", "/co", "feature/a", "2026-01-01T00:00:00")


def test_us12_release_returns_old_claim_and_deletes_file(tmp_path):
    claim = _claim("s1")
    claimfiles.create(tmp_path, "p--a.json", claim)
    assert claims.release(tmp_path, "p--a.json") == claim
    assert not (tmp_path / "p--a.json").exists()


def test_us12_release_of_nothing_returns_none(tmp_path):
    assert claims.release(tmp_path, "p--missing.json") is None


def test_us12_release_leaves_other_claims(tmp_path):
    claimfiles.create(tmp_path, "p--a.json", _claim("s1"))
    claimfiles.create(tmp_path, "p--b.json", _claim("s1"))
    claims.release(tmp_path, "p--a.json")
    assert (tmp_path / "p--b.json").exists()


def test_us13_release_session_removes_only_that_session(tmp_path):
    claimfiles.create(tmp_path, "p--a.json", _claim("s1"))
    claimfiles.create(tmp_path, "p--b.json", _claim("s2"))
    claimfiles.create(tmp_path, "p--c.json", _claim("s1"))
    removed = claims.release_session(tmp_path, "s1")
    assert sorted(removed) == ["p--a.json", "p--c.json"]
    assert sorted(p.name for p in tmp_path.iterdir()) == ["p--b.json"]


def test_us13_release_session_without_claims_returns_empty(tmp_path):
    claimfiles.create(tmp_path, "p--a.json", _claim("s2"))
    assert claims.release_session(tmp_path, "s1") == []
    assert (tmp_path / "p--a.json").exists()


def _entry(session: str, run: str) -> dict:
    return {"session": session, "run": run, "step_id": "u1-write-1", "agent": "qa"}


def _agent_files(active: Path) -> list[str]:
    return sorted(p.name for p in (active / "agents").iterdir())


def test_us20_release_removes_entries_of_the_claims_run_only(tmp_path):
    claimfiles.create(tmp_path, "p--a.json", _claim("s1"))
    agents = tmp_path / "agents"
    claimfiles.create(agents, "a1.json", _entry("s1", "run"))
    claimfiles.create(agents, "a2.json", _entry("s9", "run"))
    claimfiles.create(agents, "a3.json", _entry("s1", "other-run"))
    claims.release(tmp_path, "p--a.json")
    assert _agent_files(tmp_path) == ["a3.json"]
    assert claimfiles.read(agents, "a3.json") == _entry("s1", "other-run")


def test_us20_release_session_removes_entries_of_that_session_only(tmp_path):
    claimfiles.create(tmp_path, "p--a.json", _claim("s1"))
    agents = tmp_path / "agents"
    claimfiles.create(agents, "a1.json", _entry("s1", "run-x"))
    claimfiles.create(agents, "a2.json", _entry("s2", "run-x"))
    claimfiles.create(agents, "a3.json", _entry("s1", "run-y"))
    claims.release_session(tmp_path, "s1")
    assert _agent_files(tmp_path) == ["a2.json"]
    assert claimfiles.read(agents, "a2.json") == _entry("s2", "run-x")
