from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "scripts" / "hooks" / "claim_gate.py"


def _load(path: Path = SRC):
    spec = importlib.util.spec_from_file_location("claim_gate", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _claim(session: str, branch: str) -> dict:
    return {"session": session, "pid": 1, "branch": branch, "checkout": "/c", "since": "now"}


def test_us15_blocks_other_sessions_claim_and_names_holder():
    msg = _load().blocked("feature/x", "me", [_claim("other-sess", "feature/x")])
    assert msg is not None
    assert "other-sess" in msg and "feature/x" in msg


def test_us15_own_claim_passes():
    assert _load().blocked("feature/x", "me", [_claim("me", "feature/x")]) is None


def test_us15_claim_on_other_branch_passes():
    assert _load().blocked("feature/x", "me", [_claim("other", "feature/y")]) is None


def test_us15_no_claims_passes():
    assert _load().blocked("feature/x", "me", []) is None


def test_us15_empty_session_passes():
    assert _load().blocked("feature/x", "", [_claim("other", "feature/x")]) is None


def _setup(tmp_path: Path, branch: str, claims: list[dict]):
    hooks = tmp_path / "ws" / "scripts" / "hooks"
    hooks.mkdir(parents=True)
    shutil.copy(SRC, hooks / "claim_gate.py")
    active = tmp_path / "ws" / ".claude" / "runs" / ".active"
    active.mkdir(parents=True)
    for i, c in enumerate(claims):
        (active / f"c{i}.json").write_text(json.dumps(c))
    repo = tmp_path / "repo"
    repo.mkdir()
    for args in (["init", "-q", "-b", branch], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "i"]):
        subprocess.run(["git", *args], cwd=repo, check=True)
    return _load(hooks / "claim_gate.py"), repo


def test_us15_main_returns_1_and_prints_message_when_blocked(tmp_path, monkeypatch, capsys):
    mod, repo = _setup(tmp_path, "feature/x", [_claim("other-sess", "feature/x")])
    monkeypatch.chdir(repo)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "me")
    assert mod.main() == 1
    assert "other-sess" in capsys.readouterr().err


def test_us15_main_returns_0_for_own_claim(tmp_path, monkeypatch):
    mod, repo = _setup(tmp_path, "feature/x", [_claim("me", "feature/x")])
    monkeypatch.chdir(repo)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "me")
    assert mod.main() == 0


def test_us15_main_returns_0_without_session(tmp_path, monkeypatch):
    mod, repo = _setup(tmp_path, "feature/x", [_claim("other", "feature/x")])
    monkeypatch.chdir(repo)
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    assert mod.main() == 0


def test_us15_pre_commit_runs_claim_gate():
    assert "claim_gate.py" in (ROOT / ".githooks" / "pre-commit").read_text()


def _unborn_repo(tmp_path: Path, branch: str) -> Path:
    repo = tmp_path / "unborn"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", branch], cwd=repo, check=True)
    return repo


def test_us27_unborn_head_branch_held_by_other_session_is_refused(tmp_path, monkeypatch, capsys):
    mod, _ = _setup(tmp_path, "feature/x", [_claim("other", "feature/x")])
    repo = _unborn_repo(tmp_path, "feature/x")
    monkeypatch.chdir(repo)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "me")
    assert mod.main() == 1
    assert "other" in capsys.readouterr().err


def test_us27_unborn_head_without_claims_passes(tmp_path, monkeypatch):
    mod, _ = _setup(tmp_path, "feature/x", [])
    repo = _unborn_repo(tmp_path, "feature/x")
    monkeypatch.chdir(repo)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "me")
    assert mod.main() == 0
