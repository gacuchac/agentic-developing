from __future__ import annotations

import importlib.util
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("post_edit", _root / "scripts" / "hooks" / "post_edit.py")
post_edit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(post_edit)


def test_us37_lint_blocks_a_missing_annotation_outside_the_workspace(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    ruff = post_edit.find_ruff()
    target = tmp_path / "m.py"
    target.write_text('def add(a, b):\n    """Sum."""\n    return a + b\n')
    assert post_edit.lint(ruff, str(target)).returncode != 0
