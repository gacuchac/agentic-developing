#!/usr/bin/env python3
"""Create a project under the workspace from templates/project: its files, then a git repo with dev and uat."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
TEMPLATE = WORKSPACE / "templates" / "project"
BOT_NAME = "gacuchacbot"
BOT_EMAIL = "360311223+gacuchacbot@users.noreply.github.com"
# Copied once from the workspace at creation, then owned by the project (each project runs its own CI).
CI_FILES = (
    ".github/workflows/branch-order.yml",
    "scripts/ci/check_branch_order.py",
    "tests/test_check_branch_order.py",
)


def project_files(name: str, description: str) -> dict[str, str]:
    """Every file a new project starts with, as {path relative to the project: text}."""
    files = {}
    for src in sorted(p for p in TEMPLATE.rglob("*") if p.is_file()):
        rel = src.relative_to(TEMPLATE).as_posix()
        text = src.read_text().replace("{project}", name).replace("{description}", description)
        files[".gitignore" if rel == "gitignore" else rel] = text
    files.update({rel: (WORKSPACE / rel).read_text() for rel in CI_FILES})
    files["evals/cases/.gitkeep"] = ""
    return files


def write_files(root: Path, files: dict[str, str]) -> None:
    """Write each file under root, creating folders as needed; a file starting with `#!` is made executable."""
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text)
        if text.startswith("#!"):
            (root / rel).chmod(0o755)


def init_repo(root: Path) -> None:
    """git init on main, set the bot's no-reply identity, commit the scaffold, create dev and uat, switch to dev."""
    steps = (
        ["init", "-q", "-b", "main"],
        ["config", "user.name", BOT_NAME],
        ["config", "user.email", BOT_EMAIL],
        ["add", "-A"],
        ["commit", "-q", "-m", "X0: Start from the workspace project template"],
        ["branch", "dev"],
        ["branch", "uat"],
        ["switch", "-q", "dev"],
    )
    for step in steps:
        subprocess.run(["git", "-C", str(root), *step], check=True)


def main() -> int:
    """Create a new project from the template from the command line; return the exit code."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", help="folder name of the new project")
    parser.add_argument("description", help="one paragraph: what the project is")
    args = parser.parse_args()
    root = WORKSPACE / args.name
    if root.exists():
        sys.exit(f"{root} already exists.")
    write_files(root, project_files(args.name, args.description))
    init_repo(root)
    print(f"Created {root} on dev. Next: python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
