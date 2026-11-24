"""Claim records that mark which session is working on a task."""

from __future__ import annotations

from collections.abc import Callable
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


def acquire(
    active: Path,
    name: str,
    claim: dict,
    alive: Callable[[int], bool],
    start: Callable[[int], str | None],
    log: Callable[[str], None],
) -> tuple[str, dict | None]:
    """Claim `name` in `active`; return (outcome, holder).

    "created": no claim existed. "own": the claim has this session; run, checkout and branch are refreshed.
    "taken_over": the claim was stale, replaced and logged. "refused": a live session holds it; holder is that claim.
    """
    if claimfiles.create(active, name, claim):
        return "created", None
    held = claimfiles.read(active, name)
    if held is not None and held["session"] == claim["session"]:
        refreshed = {**held, **{key: claim[key] for key in ("run", "checkout", "branch")}}
        _replace(active, name, refreshed)
        return "own", refreshed
    if held is not None and not is_stale(held, alive(held["pid"]), start(held["pid"])):
        return "refused", held
    log(f"takeover {name} from {(held or {}).get('session')}")
    _replace(active, name, claim)
    return "taken_over", held
