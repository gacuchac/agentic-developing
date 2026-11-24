"""Auto-node handlers of the workflow engine: each reads the state and returns (outcome, entry fields, new state)."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import units


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


Handler = Callable[[dict, Ctx], tuple[str, dict, dict]]


def _fix(state: dict, ctx: Ctx) -> tuple[str, list[str]]:
    decision = [e for e in state["history"] if "decision" in e][-1]["evidence"]
    if "tests" in decision:
        return "full-suite " + " ".join(decision["tests"]), decision["tests"]
    ids = decision["findings"]
    reviews = [r for e in state["history"] if "reviews" in e for r in e["reviews"]]
    hit = [r for r in reviews if set(r["fails"]) & set(ids)]
    text = "\n".join((ctx.run / r["review"]).read_text() for r in hit)
    lines = [ln for ln in text.splitlines() if ln.split(":")[0] in ids]
    return " ".join(sorted({r["pass"] for r in hit})) + " " + " ".join(ids), lines


def _write_unit(state: dict, ctx: Ctx) -> tuple[str, dict, dict]:
    """Write run/unit.md: the plan unit, or its fix text after a decision; outcome `done`."""
    unit = units.plan_units((ctx.run / state["plan"]).read_text())[state["unit"] - 1]
    if state["fix"]:
        fix, lines = _fix(state, ctx)
        unit = units.fix_text(unit, f"{fix} on {state['head']}", lines)
    (ctx.run / "unit.md").write_text(unit)
    return "done", {}, state


def _next_unit(state: dict, ctx: Ctx) -> tuple[str, dict, dict]:
    """Return `finished` in the finish stage, `more` with the next unit and fix 0, else `last`."""
    if state["stage"] == "finish":
        return "finished", {}, state
    if state["unit"] < len(units.plan_units((ctx.run / state["plan"]).read_text())):
        return "more", {}, {**state, "unit": state["unit"] + 1, "fix": 0}
    return "last", {}, state


def _result(state: dict, node: str) -> dict:
    return [e for e in state["history"] if e.get("node") == node and "result" in e][-1]["result"]


def _red_run(state: dict, ctx: Ctx) -> tuple[str, dict, dict]:
    """Run qa's added tests; `expected` when all fail and qa's reason is expected, else `unexpected`."""
    qa = _result(state, "qa_write")
    added = qa["tests_added"]
    failed = ctx.tests(ctx.repo, added)["failed"]
    red = {"tests": added, "failed": failed, "claimed": qa["red_run"]}
    (ctx.run / "red.json").write_text(json.dumps(red))
    covered = bool(added) and all(t in failed or t.split("::")[0] in failed for t in added)
    return ("expected" if covered and qa["red_run"]["reason_expected"] else "unexpected"), red, state


HANDLERS: dict[str, Handler] = {
    "write_unit": _write_unit,
    "next_unit": _next_unit,
    "red_run": _red_run,
}
