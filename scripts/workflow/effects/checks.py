"""Run a repo's pytest and read the failing test ids."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

_FAILURE_LINE = re.compile(r"^(?:FAILED|ERROR) (\S+)", re.M)


def failed_ids(output: str) -> list[str]:
    """Return the ids of the FAILED and ERROR lines of pytest's -rfE summary."""
    return _FAILURE_LINE.findall(output)


def all_red(tests: list[str], failed: list[str]) -> bool:
    """True when tests is non-empty and each test, or its file, is in failed."""
    return bool(tests) and all(t in failed or t.split("::")[0] in failed for t in tests)


def run_pytest(repo: Path, targets: list[str], python: Path | None = None) -> dict:
    """Run pytest on targets in repo; return {"code": exit code, "failed": failing ids}."""
    venv_python = repo / ".venv" / "bin" / "python"
    interpreter = python or (venv_python if venv_python.exists() else Path(sys.executable))
    proc = subprocess.run(
        [str(interpreter), "-m", "pytest", "-q", "-rfE", *targets],
        cwd=repo, capture_output=True, text=True, check=False,
    )
    return {"code": proc.returncode, "failed": failed_ids(proc.stdout)}
