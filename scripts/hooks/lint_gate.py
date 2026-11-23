#!/usr/bin/env python3
"""Pre-commit check: run ruff and the slop checks on the staged Python files."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from post_edit import find_ruff  # noqa: E402
from slop_checks import check_source  # noqa: E402


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


def staged_names() -> list[str]:
    """Names of the added, copied, modified or renamed files staged in the current repo."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.splitlines()


def staged_source(name: str) -> str:
    """The staged (index) content of the file `name`."""
    return subprocess.run(["git", "show", f":{name}"], capture_output=True, text=True, check=True).stdout


def ruff_failed(sources: dict[str, str]) -> bool:
    """Run ruff check on each staged source by its name and print the findings; True if any."""
    ruff = find_ruff()
    if ruff is None:
        print("lint_gate: ruff not found, skipping ruff check", file=sys.stderr)
        return False
    failed = False
    for name, source in sources.items():
        result = subprocess.run(
            [ruff, "check", "--stdin-filename", name, "-"], input=source, capture_output=True, text=True, check=False
        )
        if result.returncode != 0:
            print(result.stdout or result.stderr)
            failed = True
    return failed


def slop_failed(sources: dict[str, str]) -> bool:
    """Print the slop findings for each staged source; True if there were any."""
    found = False
    for name, source in sources.items():
        for line, message in check_source(source, Path(name)):
            print(f"{name}:{line}: {message}")
            found = True
    return found


def main() -> int:
    """Check the staged Python files with ruff and the slop checks; return 1 on any finding, else 0."""
    sources = {name: staged_source(name) for name in python_paths(staged_names(), Path.cwd())}
    if not sources:
        return 0
    ruff_bad = ruff_failed(sources)
    slop_bad = slop_failed(sources)
    return 1 if ruff_bad or slop_bad else 0


if __name__ == "__main__":
    sys.exit(main())
