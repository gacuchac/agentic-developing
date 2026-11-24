"""Claim records that mark which session is working on a task."""

from __future__ import annotations

from pathlib import Path

from effects import claimfiles


def claim_name(project: str, task: str) -> str:
    """Return the claim file name for a project's task: "<project>--<task>.json"."""
    return f"{project}--{task}.json"


def make_claim(session: str, pid: int, pid_start: str, run: str, checkout: str, branch: str, since: str) -> dict:
    """Return a claim dict with exactly the keys session, pid, pid_start, run, checkout, branch and since."""
    return {
        "session": session,
        "pid": pid,
        "pid_start": pid_start,
        "run": run,
        "checkout": checkout,
        "branch": branch,
        "since": since,
    }


def is_stale(claim: dict, alive: bool, start: str | None) -> bool:
    """Return True when the claim's process is dead or its pid was reused (start differs from claim["pid_start"])."""
    return not alive or start != claim["pid_start"]


def _replace(active: Path, name: str, claim: dict) -> None:
    """Replace the claim file `name` in `active` with `claim`."""
    claimfiles.remove(active, name)
    claimfiles.create(active, name, claim)
