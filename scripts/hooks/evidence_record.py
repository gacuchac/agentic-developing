from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
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


def failing_fields(record: dict) -> list[str]:
    """Return the names of the fields of a full `record` that keep it from being complete."""
    added = set(record["added"])
    ok = {
        "added": bool(added) or not record["code_changed"],
        "red": added <= set(record["red"]),
        "green": added <= set(record["green"]),
        "failed": set(record["failed"]) <= set(record["breaks"]),
        "tests_touched": not record["tests_touched"],
        "uncovered": not record["uncovered"],
    }
    return [name for name, good in ok.items() if not good]


def complete(record: dict) -> bool:
    """Return True when every field is present and none keeps the record from being complete."""
    return all(f in record for f in _FIELDS) and not failing_fields(record)


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


def is_failed(test_id: str, failed: list[str]) -> bool:
    """Return True when `failed` has `test_id` itself or one of its parametrized cases `test_id[...]`."""
    return any(f == test_id or f.startswith(test_id + "[") for f in failed)


def failures_at(repo: Path, commit: str, targets: list[str], python: Path) -> list[str]:
    """Return the ids failing when pytest runs `targets` (all tests if empty) in a worktree of `repo` at `commit`."""
    checks = load_module(_SCRIPTS / "workflow" / "effects" / "checks.py")
    with _in(repo), load_module(_SCRIPTS / "codex_review.py").review_tree(commit) as tree:
        return checks.run_pytest(tree, targets, python)["failed"]


def measure(repo: Path, run: Path, sha: str, python: Path) -> dict:
    """Return the evidence record of the fix commit `sha` in `repo` (fields: see architecture.md)."""
    contracts = load_module(_SCRIPTS / "workflow" / "contracts.py")
    commit = tests_commit(repo, sha)
    added = added_tests(_git(repo, "show", "--format=", commit)) if commit else []
    span = f"{commit}..{sha}" if commit else f"{sha}^..{sha}"
    failed = failures_at(repo, sha, [], python)
    names = contracts.changed_signatures(_git(repo, "diff", span))
    paths = _git(repo, "show", "--name-only", "--format=", sha).split()
    return {
        "tests_commit": commit,
        "added": added,
        "red": [t for t in added if is_failed(t, failures_at(repo, commit, added, python))],
        "green": [t for t in added if not is_failed(t, failed)],
        "failed": failed,
        "breaks": declared_breaks(run),
        "tests_touched": [p for p in _git(repo, "diff", "--name-only", span).split() if "tests" in Path(p).parts[:-1]],
        "uncovered": sorted(contracts.uncovered(names, (run / "architecture.md").read_text())),
        "code_changed": any("tests" not in Path(p).parts[:-1] and not p.endswith(".md") for p in paths),
    }


def main(argv: list[str] | None = None) -> int:
    """Run `write --run <run> [--sha] [--python]` in the current repo; return 0 when the record is complete."""
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["write"])
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--sha", default="HEAD")
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    args = parser.parse_args(argv)
    sha = _git(Path.cwd(), "rev-parse", args.sha).strip()
    record = measure(Path.cwd(), args.run, sha, args.python)
    (args.run / f"evidence-{sha}.json").write_text(json.dumps(record, indent=2))
    failing = failing_fields(record)
    if failing:
        print("incomplete: " + ", ".join(failing))
    return int(bool(failing))


if __name__ == "__main__":
    sys.exit(main())
