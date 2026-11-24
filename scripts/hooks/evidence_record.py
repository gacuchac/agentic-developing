from __future__ import annotations

import importlib.util
import os
import re
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType

_SCRIPTS = Path(__file__).resolve().parents[1]

_TEST_DEF = re.compile(r"^\+(?:async )?def (test_\w*)")
_FIELDS = ("code_changed", "added", "red", "green", "failed", "breaks", "tests_touched", "uncovered")


def added_tests(diff: str) -> list[str]:
    """Return `file::name` for each test function a diff adds under a `tests` directory."""
    found, path = [], ""
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            path = line[6:]
        elif (match := _TEST_DEF.match(line)) and "tests" in path.split("/")[:-1]:
            found.append(f"{path}::{match.group(1)}")
    return found


def complete(record: dict) -> bool:
    """Return True when added tests are red and green and nothing stray failed, changed or is uncovered."""
    added = set(record.get("added", ()))
    return (
        all(f in record for f in _FIELDS)
        and (bool(added) or not record["code_changed"])
        and added <= set(record["red"]) & set(record["green"])
        and set(record["failed"]) <= set(record["breaks"])
        and not (record["tests_touched"] or record["uncovered"])
    )


def load_module(path: Path) -> ModuleType:
    """Return the module loaded from the file at `path`."""
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def tests_commit(repo: Path, sha: str) -> str | None:
    """Return the newest `test(` commit before `sha` and after the previous non-test commit, or None."""
    cmd = ["git", "log", "--max-count=1", "--skip=1", "--format=%H %s", sha]
    commit, _, subject = subprocess.run(cmd, cwd=repo, check=True, capture_output=True, text=True).stdout.partition(" ")
    return commit if subject.startswith("test(") else None


def declared_breaks(run: Path) -> list[str]:
    """Return the test ids on the `Breaks:` line of `run/unit.md`, or an empty list."""
    for line in (run / "unit.md").read_text().splitlines():
        if line.startswith("Breaks:"):
            return [item.strip() for item in line[7:].split(",") if item.strip()]
    return []


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout


@contextmanager
def _in(repo: Path) -> Iterator[None]:
    before = os.getcwd()
    os.chdir(repo)
    try:
        yield
    finally:
        os.chdir(before)


def red_ids(repo: Path, commit: str, added: list[str], python: Path) -> list[str]:
    """Return the `added` test ids that fail in a worktree of `repo` at `commit`."""
    checks = load_module(_SCRIPTS / "workflow" / "effects" / "checks.py")
    with _in(repo), load_module(_SCRIPTS / "codex_review.py").review_tree(commit) as tree:
        failed = checks.run_pytest(tree, added, python)["failed"]
    return [t for t in added if any(f.startswith(t) for f in failed)]
