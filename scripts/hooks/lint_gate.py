#!/usr/bin/env python3
"""Pre-commit check: run ruff and the slop checks on the staged Python files."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def is_python(path: Path) -> bool:
    """True for a .py file, or a suffixless file whose shebang line names python."""
    if path.suffix:
        return path.suffix == ".py"
    with path.open("rb") as handle:
        first = handle.readline()
    return first.startswith(b"#!") and b"python" in first


def python_paths(names: list[str], root: Path) -> list[str]:
    """The names (relative to root) that exist and are Python files, in order."""
    return [name for name in names if (root / name).is_file() and is_python(root / name)]
