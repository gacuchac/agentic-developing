from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import claims
from effects import claimfiles

_path = Path(__file__).resolve().parents[1] / "scripts" / "hooks" / "session_end.py"


def _load():
    spec = importlib.util.spec_from_file_location("session_end", _path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _claim(session: str) -> dict:
    return claims.make_claim(session, 1, "start", "run", "/co", "feature/a", "2026-01-01T00:00:00")


def test_us14_ending_session_frees_only_its_own_claims(tmp_path):
    claimfiles.create(tmp_path, "p--a.json", _claim("s1"))
    claimfiles.create(tmp_path, "p--b.json", _claim("s1"))
    claimfiles.create(tmp_path, "p--c.json", _claim("s2"))
    assert _load().main(json.dumps({"session_id": "s1"}), tmp_path) == 0
    assert sorted(p.name for p in tmp_path.iterdir()) == ["p--c.json"]


def test_us14_garbage_stdin_returns_zero_and_keeps_claims(tmp_path):
    claimfiles.create(tmp_path, "p--a.json", _claim("s1"))
    module = _load()
    for bad in ("", "not json", "[]", "{}", '{"session_id": 5}'):
        assert module.main(bad, tmp_path) == 0
    assert (tmp_path / "p--a.json").exists()


def test_us14_missing_active_folder_returns_zero(tmp_path):
    assert _load().main(json.dumps({"session_id": "s1"}), tmp_path / "none") == 0
