from __future__ import annotations

import argparse
import ast
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


def _test_sources(source: str) -> dict[str, str]:
    tree = ast.parse(source)
    return {
        n.name: ast.get_source_segment(source, n) or ""
        for n in tree.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith("test")
    }


def changed_tests(before: str | None, after: str, path: str) -> list[str]:
    """Return `path::name` of each top-level test function in `after` that is new or edited.

    `before` None means every test is new. Order is as in `after`.
    """
    old = _test_sources(before) if before is not None else {}
    return [f"{path}::{name}" for name, text in _test_sources(after).items() if old.get(name) != text]


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


def subtract_record(sha: str, touched: list[str], failed: list[str]) -> dict:
    """Return the evidence record of a clean-up commit `sha`: tests it touched and tests failing in the suite."""
    return {"kind": "subtract", "sha": sha, "tests_touched": touched, "suite_failed": failed}


def complete(record: dict) -> bool:
    """Return True for a subtract record with a sha and no touched or failed tests, else when a unit record passes."""
    if record.get("kind") == "subtract":
        return bool(record["sha"]) and not record["tests_touched"] and not record["suite_failed"]
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
    """Return True when `failed` has `test_id`, one of its parametrized cases `test_id[...]`, or its file."""
    file_id = test_id.split("::")[0]
    return any(f in (test_id, file_id) or f.startswith(test_id + "[") for f in failed)


def failures_at(repo: Path, commit: str, targets: list[str], python: Path) -> list[str]:
    """Return the ids failing when pytest runs `targets` (all tests if empty) in a worktree of `repo` at `commit`."""
    checks = load_module(_SCRIPTS / "workflow" / "effects" / "checks.py")
    with _in(repo), load_module(_SCRIPTS / "codex_review.py").review_tree(commit) as tree:
        return checks.run_pytest(tree, targets, python)["failed"]


def failures_with_tests(
    repo: Path, commit: str, sha: str, paths: list[str], targets: list[str], python: Path
) -> list[str]:
    """Return the ids failing when `targets` run in a worktree at `commit` with files `paths` as at `sha`."""
    checks = load_module(_SCRIPTS / "workflow" / "effects" / "checks.py")
    with _in(repo), load_module(_SCRIPTS / "codex_review.py").review_tree(commit) as tree:
        for path in paths:
            (tree / path).parent.mkdir(parents=True, exist_ok=True)
            (tree / path).write_text(_git(repo, "show", f"{sha}:{path}"))
        return checks.run_pytest(tree, targets, python)["failed"]


def _test_files(repo: Path, commit: str, sha: str) -> list[str]:
    log = _git(repo, "log", "--format=%H %s", f"{commit}^..{sha}").splitlines()
    shas = [line.split()[0] for line in log if line.partition(" ")[2].startswith("test(")]
    paths = {p for s in shas for p in _git(repo, "show", "--name-only", "--format=", s).split()}
    return sorted(p for p in paths if "tests" in Path(p).parts[:-1] and p.endswith(".py"))


def _file_at(repo: Path, rev: str, path: str) -> str | None:
    shown = subprocess.run(["git", "show", f"{rev}:{path}"], cwd=repo, capture_output=True, text=True)
    return shown.stdout if shown.returncode == 0 else None


def _changed_in_unit(repo: Path, commit: str, sha: str, paths: list[str]) -> list[str]:
    found = []
    for path in paths:
        after = _file_at(repo, sha, path)
        if after is not None:
            found += changed_tests(_file_at(repo, f"{commit}^", path), after, path)
    return found


def _first_test_commit(repo: Path, commit: str | None) -> str | None:
    while commit:
        parent = tests_commit(repo, commit)
        if not parent:
            break
        commit = parent
    return commit


def _test_commit(repo: Path, sha: str, given: str | None) -> str | None:
    if given:
        return _git(repo, "rev-parse", given).strip()
    return _first_test_commit(repo, tests_commit(repo, sha))


def _touched_tests(repo: Path, commit: str | None, sha: str) -> list[str]:
    base = commit or f"{sha}^"
    if commit:
        log = _git(repo, "log", "--format=%H %s", f"{commit}..{sha}").splitlines()
        base = next((line.split()[0] for line in log if line.partition(" ")[2].startswith("test(")), commit)
    paths = _git(repo, "diff", "--name-only", base, sha).split()
    return [p for p in paths if "tests" in Path(p).parts[:-1]]


def _architecture(run: Path) -> str:
    path = run / "architecture.md"
    return path.read_text() if path.is_file() else ""


def measure(repo: Path, run: Path, sha: str, python: Path, tests_commit: str | None = None) -> dict:
    """Return the evidence record of the fix commit `sha` in `repo` (fields: see architecture.md).

    `tests_commit` (full or short sha) names the test commit; when None it is discovered before `sha`.
    """
    contracts = load_module(_SCRIPTS / "workflow" / "contracts.py")
    commit = _test_commit(repo, sha, tests_commit)
    test_files = _test_files(repo, commit, sha) if commit else []
    added = _changed_in_unit(repo, commit, sha, test_files) if commit else []
    span = f"{commit}..{sha}" if commit else f"{sha}^..{sha}"
    failed = failures_at(repo, sha, [], python)
    names = contracts.changed_signatures(_git(repo, "diff", span))
    paths = _git(repo, "show", "--name-only", "--format=", sha).split()
    red_failures = failures_with_tests(repo, commit, sha, test_files, added, python) if added else []
    return {
        "tests_commit": commit,
        "added": added,
        "red": [t for t in added if is_failed(t, red_failures)],
        "green": [t for t in added if not is_failed(t, failed)],
        "failed": failed,
        "breaks": declared_breaks(run),
        "tests_touched": _touched_tests(repo, commit, sha),
        "uncovered": sorted(contracts.uncovered(names, _architecture(run))),
        "code_changed": any("tests" not in Path(p).parts[:-1] and not p.endswith(".md") for p in paths),
    }


def main(argv: list[str] | None = None) -> int:
    """Run `write --run <run> [--sha] [--python] [--tests-commit]`; return 0 when the record is complete."""
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["write"])
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--sha", default="HEAD")
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--tests-commit")
    args = parser.parse_args(argv)
    sha = _git(Path.cwd(), "rev-parse", args.sha).strip()
    record = measure(Path.cwd(), args.run, sha, args.python, args.tests_commit)
    (args.run / f"evidence-{sha}.json").write_text(json.dumps(record, indent=2))
    failing = failing_fields(record)
    if failing:
        print("incomplete: " + ", ".join(failing))
    return int(bool(failing))


if __name__ == "__main__":
    sys.exit(main())
