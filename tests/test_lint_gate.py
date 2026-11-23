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


def _write_only(repo: Path, name: str, text: str) -> None:
    (repo / name).write_text(text)


def test_x8_staged_ruff_error_blocks_even_if_working_tree_fixed(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    _stage(repo, "m.py", RUFF_ERROR)
    _write_only(repo, "m.py", CLEAN)
    assert _gate(repo, monkeypatch) == 1


def test_x8_staged_slop_blocks_even_if_working_tree_fixed(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    _stage(repo, "m.py", SLOP)
    _write_only(repo, "m.py", CLEAN)
    assert _gate(repo, monkeypatch) == 1


def test_x8_staged_clean_passes_even_if_working_tree_broken(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    _stage(repo, "m.py", CLEAN)
    _write_only(repo, "m.py", RUFF_ERROR + SLOP)
    assert _gate(repo, monkeypatch) == 0


def test_x8_staged_shebang_file_checked_from_staged_content(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    _stage(repo, "bin/tool", "#!/usr/bin/env python3\n" + SLOP, 0o755)
    _write_only(repo, "bin/tool", "#!/usr/bin/env python3\n" + CLEAN)
    assert _gate(repo, monkeypatch) == 1


def test_x8_is_python_source_py_suffix():
    assert gate.is_python_source("a/b.py", "anything\n") is True


def test_x8_is_python_source_suffixless_python_shebang():
    assert gate.is_python_source("tool", "#!/usr/bin/env python3\nprint(1)\n") is True
    assert gate.is_python_source("tool", "#!/usr/bin/python\n") is True


def test_x8_is_python_source_rejects_non_python():
    assert gate.is_python_source("run", "#!/bin/sh\necho 1\n") is False
    assert gate.is_python_source("plain", "just text\n") is False
    assert gate.is_python_source("plain", "") is False
    assert gate.is_python_source("README.md", "#!/usr/bin/env python3\n") is False
    assert gate.is_python_source("tool", "x = 1\n#!/usr/bin/env python3\n") is False


def test_x8_staged_shebang_blocks_even_if_working_tree_loses_shebang(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    _stage(repo, "bin/tool", "#!/usr/bin/env python3\n" + SLOP, 0o755)
    _write_only(repo, "bin/tool", "plain text\n")
    assert _gate(repo, monkeypatch) == 1


def test_x8_staged_file_deleted_from_working_tree_is_still_checked(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    _stage(repo, "m.py", RUFF_ERROR)
    (repo / "m.py").unlink()
    assert _gate(repo, monkeypatch) == 1


def test_x8_staged_binary_file_does_not_crash(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    (repo / "blob.bin").write_bytes(b"\xff\xfe\x00\x80\x81binary")
    subprocess.run(["git", "-C", str(repo), "add", "blob.bin"], check=True)
    assert _gate(repo, monkeypatch) == 0


def test_x8_staged_binary_with_py_suffix_does_not_crash(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    (repo / "blob.py").write_bytes(b"\xff\xfe\x00\x80\x81")
    subprocess.run(["git", "-C", str(repo), "add", "blob.py"], check=True)
    assert _gate(repo, monkeypatch) in (0, 1)


def test_x8_staged_suffixless_binary_does_not_crash(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    (repo / "blob").write_bytes(b"\xff\xfe\x00\x80\x81binary")
    subprocess.run(["git", "-C", str(repo), "add", "blob"], check=True)
    assert _gate(repo, monkeypatch) == 0
