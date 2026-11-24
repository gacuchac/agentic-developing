"""Auto-node handlers of the workflow engine: each reads the state and returns (outcome, entry fields, new state)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Ctx:
    """The run's folders and the effects (reviews, tests, git, clock) a handler may use."""

    run: Path
    repo: Path
    python: Path
    start_review: Callable[[list[str], Path, Path], dict]
    collect_review: Callable[[dict], Path | None]
    run_review: Callable[[list[str], Path], Path | None]
    tests: Callable[[Path, list[str]], dict]
    touched: Callable[[Path], list[str]]
    source: Callable[[Path, str | None, str | None], str]
    commit: Callable[[Path, str, list[str] | None], str]
    evidence: Callable[[Path, Path, str, Path], dict]
    diff: Callable[[Path], str]
    file_at: Callable[[Path, str, str | None], str | None]
    log: Callable[[Path, list[str]], None]
    now: Callable[[], str]
