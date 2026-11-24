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
