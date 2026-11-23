#!/usr/bin/env python3
"""Pre-commit check: block a commit whose staged changes exceed MAX_LINES lines.

Tests and documentation don't count.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path, PurePosixPath

MAX_LINES = 30


def file_counts(numstat: str) -> dict[str, int]:
    """Changed lines per file from `git diff --numstat` output.

    Each file counts max(added, deleted), so editing one line counts 1. A pure
    rename counts 0 and a binary file ("-" in numstat) counts 1.
    """
    counts: dict[str, int] = {}
    for line in filter(None, numstat.splitlines()):
        added, deleted, path = line.split("\t", 2)
        counts[path] = 1 if added == "-" else max(int(added), int(deleted))
    return counts


def without_deleted_files(counts: dict[str, int], name_status: str) -> dict[str, int]:
    """counts with each wholly deleted file counted 0: deleting is not a change.

    Deleted means status D in `git diff --name-status`.
    """
    deleted = {line.split("\t", 1)[1] for line in name_status.splitlines() if line.startswith("D\t")}
    return {path: 0 if path in deleted else n for path, n in counts.items()}


def without_test_files(counts: dict[str, int]) -> dict[str, int]:
    """counts with every path under a `tests` directory counted 0.

    Tests don't count toward the cap.
    """
    return {path: 0 if "tests" in PurePosixPath(path).parts[:-1] else n for path, n in counts.items()}


DOC_SUFFIXES = {".md", ".txt", ".rst"}


def without_doc_files(counts: dict[str, int]) -> dict[str, int]:
    """counts with every .md, .txt or .rst path (any case) and every LICENSE file counted 0.

    Documentation doesn't count toward the cap.
    """
    docs = {p for p in counts if PurePosixPath(p).suffix.lower() in DOC_SUFFIXES or PurePosixPath(p).name == "LICENSE"}
    return {path: 0 if path in docs else n for path, n in counts.items()}


def count_changed_lines(numstat: str) -> int:
    """Total changed lines over all files, counted as in file_counts."""
    return sum(file_counts(numstat).values())


def git(*args: str) -> str:
    """Run a git command in the current repo and return stdout."""
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout


def merge_in_progress(git_dir: Path) -> bool:
    """True while git is finishing a merge, which the cap exempts."""
    return (git_dir / "MERGE_HEAD").exists()


def first_commit() -> bool:
    """True when the repo has no commits yet: its first commit is the project scaffold, which the cap exempts."""
    return (
        subprocess.run(["git", "rev-parse", "--verify", "-q", "HEAD"], capture_output=True, check=False).returncode != 0
    )


def main() -> int:
    """Exit 0 when the staged changes fit in MAX_LINES (or finish a merge or make the first commit), else exit 1."""
    if first_commit() or merge_in_progress(Path(git("rev-parse", "--git-dir").strip())):
        return 0
    numstat, name_status = (git("diff", "--cached", flag, "-M") for flag in ("--numstat", "--name-status"))
    counts = without_doc_files(without_test_files(without_deleted_files(file_counts(numstat), name_status)))
    if sum(counts.values()) <= MAX_LINES:
        return 0
    lines = "\n".join(f"  {n:4d}  {path}" for path, n in counts.items())
    print(
        f"Commit blocked: {sum(counts.values())} changed lines, limit {MAX_LINES}.\n{lines}\n"
        "Split it into smaller commits, each achieving one thing.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
