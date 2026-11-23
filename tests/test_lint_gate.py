from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
_path = _root / "scripts" / "hooks" / "lint_gate.py"
_spec = importlib.util.spec_from_file_location("lint_gate", _path)
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)

CLEAN = "def add(a: int, b: int) -> int:\n    return a + b\n"
SLOP = "ITEMS = []\n\n\ndef add(x):\n    ITEMS.append(x)\n"
RUFF_ERROR = "import os\n\n\ndef f() -> int:\n    return 1\n"


def _repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    return tmp_path


def _stage(repo: Path, name: str, text: str, mode: int | None = None) -> None:
    target = repo / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)
    if mode is not None:
        target.chmod(mode)
    subprocess.run(["git", "-C", str(repo), "add", name], check=True)


def _gate(repo: Path, monkeypatch) -> int:
    monkeypatch.chdir(repo)
    return gate.main()


def test_x4_python_paths_keeps_python_existing_names_in_order(tmp_path):
    (tmp_path / "b.py").write_text(CLEAN)
    (tmp_path / "a.py").write_text(CLEAN)
    (tmp_path / "notes.md").write_text("hi\n")
    (tmp_path / "tool").write_text("#!/usr/bin/env python3\nprint(1)\n")
    (tmp_path / "run").write_text("#!/bin/sh\necho 1\n")
    (tmp_path / "plain").write_text("just text\n")
    names = ["b.py", "notes.md", "gone.py", "tool", "run", "plain", "a.py"]
    assert gate.python_paths(names, tmp_path) == ["b.py", "tool", "a.py"]


def test_x4_python_paths_empty_input(tmp_path):
    assert gate.python_paths([], tmp_path) == []


def test_x4_clean_staged_python_passes(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    _stage(repo, "ok.py", CLEAN)
    assert _gate(repo, monkeypatch) == 0


def test_x4_slop_finding_blocks(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    _stage(repo, "bad.py", SLOP)
    assert _gate(repo, monkeypatch) == 1


def test_x4_ruff_error_blocks(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    _stage(repo, "unused.py", RUFF_ERROR)
    assert _gate(repo, monkeypatch) == 1


def test_x4_only_markdown_staged_passes(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    _stage(repo, "README.md", "# hi\n")
    assert _gate(repo, monkeypatch) == 0


def test_x4_nothing_staged_passes(tmp_path, monkeypatch):
    assert _gate(_repo(tmp_path), monkeypatch) == 0


def test_x4_extensionless_python_shebang_file_is_checked(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    _stage(repo, "bin/tool", "#!/usr/bin/env python3\n" + SLOP, 0o755)
    assert _gate(repo, monkeypatch) == 1


def test_x4_extensionless_non_python_file_is_ignored(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    _stage(repo, "bin/run", "#!/bin/sh\nITEMS=1\n", 0o755)
    assert _gate(repo, monkeypatch) == 0
