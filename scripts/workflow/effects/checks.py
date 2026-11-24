"""Run a repo's pytest, read the failing test ids and measure a pending change."""
from __future__ import annotations

import contextlib
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_FAILURE_LINE = re.compile(r"^(?:FAILED|ERROR) (.+?)(?: - .*)?$", re.M)


def failed_ids(output: str) -> list[str]:
    """Return the ids of the FAILED and ERROR lines of pytest's -rfE summary."""
    return _FAILURE_LINE.findall(output)


def all_red(tests: list[str], failed: list[str]) -> bool:
    """True when tests is non-empty and each test, or its file, is in failed."""
    return bool(tests) and all(t in failed or t.split("::")[0] in failed for t in tests)


def run_pytest(repo: Path, targets: list[str], python: Path | None = None) -> dict:
    """Run pytest on targets in repo; return {"code": exit code, "failed": failing ids}.

    A non-zero exit that names no failing test gives one entry, `pytest exit <code>: <last output line>`.
    """
    venv_python = repo / ".venv" / "bin" / "python"
    interpreter = python or (venv_python if venv_python.exists() else Path(sys.executable))
    proc = subprocess.run(
        [str(interpreter), "-m", "pytest", "-q", "-rfE", *targets],
        cwd=repo, capture_output=True, text=True, check=False,
    )
    failed = failed_ids(proc.stdout)
    if proc.returncode and not failed:
        lines = [line for line in (proc.stdout + proc.stderr).splitlines() if line.strip()]
        failed = [f"pytest exit {proc.returncode}: {lines[-1] if lines else ''}"]
    return {"code": proc.returncode, "failed": failed}


def tests_touched(repo: Path) -> list[str]:
    """Return paths with a `tests` directory component that differ from HEAD, untracked included."""
    def git(*args: str) -> list[str]:
        out = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True)
        return out.stdout.splitlines()

    paths = git("diff", "--name-only", "HEAD") + git("ls-files", "--others", "--exclude-standard")
    return [p for p in paths if "tests" in Path(p).parent.parts]


def fix_imports(repo: Path, paths: list[str]) -> None:
    """Sort the import blocks of paths in repo with ruff and the workspace ruff.toml; never raises."""
    config = Path(__file__).resolve().parents[3] / "ruff.toml"
    with contextlib.suppress(OSError):
        subprocess.run(
            ["ruff", "check", "--fix", "--select", "I", "--config", str(config), *paths],
            cwd=repo, capture_output=True, check=False,
        )


def _hook(name: str) -> object:
    path = Path(__file__).resolve().parents[2] / "hooks" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _pending_diffs(repo: Path, *flags: str) -> list[str]:
    """Return `git diff --cached -M <flag> HEAD` per flag, with untracked files added to a copy of the index."""
    with tempfile.TemporaryDirectory() as tmp:
        index = Path(tmp) / "index"
        real_index = Path(subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-path", "index"],
            cwd=repo, capture_output=True, text=True, check=True,
        ).stdout.strip())
        if real_index.exists():
            shutil.copy(real_index, index)
        env = {**os.environ, "GIT_INDEX_FILE": str(index)}

        def git(*args: str) -> str:
            return subprocess.run(["git", *args], cwd=repo, env=env, capture_output=True, text=True, check=True).stdout

        git("add", "-A")
        return [git("diff", "--cached", *([flag] if flag else []), "-M", "HEAD") for flag in flags]


def added_tests(repo: Path) -> list[str]:
    """Return the ids (`<path>::<name>`) of the test functions repo's uncommitted changes add against HEAD.

    Untracked test files are included. The repo's own index is not touched.
    """
    (diff,) = _pending_diffs(repo, "")
    return _hook("evidence_record").added_tests(diff)


def change_size(repo: Path) -> dict[str, int]:
    """Return the changed lines per file of repo's uncommitted changes against HEAD, untracked files included.

    Counted with the rules of scripts/hooks/commit_cap.py: deleted, test, document and skill files and files
    counting 0 are left out. The repo's own index is not touched.
    """
    cap = _hook("commit_cap")
    numstat, name_status = _pending_diffs(repo, "--numstat", "--name-status")
    counts = cap.without_deleted_files(cap.file_counts(numstat), name_status)
    counts = cap.without_skill_files(cap.without_doc_files(cap.without_test_files(counts)))
    return {path: n for path, n in counts.items() if n}
