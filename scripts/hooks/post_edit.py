#!/usr/bin/env python3
"""PostToolUse hook: format and lint a Python file Claude just edited; exit 2 shows problems to Claude."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def edited_path(event: dict) -> str:
    """Path of the edited file from the hook's JSON input."""
    return event.get("tool_input", {}).get("file_path", "")


def find_ruff() -> str | None:
    """Path to ruff on PATH or in the usual Homebrew folders, which VS Code's PATH often lacks."""
    return shutil.which("ruff", path=f"{os.environ.get('PATH', '')}:/opt/homebrew/bin:/usr/local/bin")


def workspace_ruff_config() -> Path:
    """Path of the workspace's ruff.toml, two folders above this file's folder."""
    return Path(__file__).resolve().parents[2] / "ruff.toml"


def lint(ruff: str, path: str) -> subprocess.CompletedProcess:
    """Format the file, then lint it, both with the workspace ruff config."""
    config = str(workspace_ruff_config())
    subprocess.run([ruff, "format", "--config", config, path], capture_output=True, check=False)
    return subprocess.run([ruff, "check", "--config", config, path], capture_output=True, text=True, check=False)


def main() -> int:
    """Hook entry point: format and lint the edited .py file named on stdin; return the exit code."""
    path = edited_path(json.load(sys.stdin))
    ruff = find_ruff()
    if not path.endswith(".py") or ruff is None:
        return 0
    result = lint(ruff, path)
    if result.returncode == 0:
        return 0
    print(result.stdout or result.stderr, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
