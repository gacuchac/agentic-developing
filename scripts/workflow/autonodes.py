"""Auto-node handlers of the workflow engine: each reads the state and returns (outcome, entry fields, new state)."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import graph
import review
import state as st
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
    evidence: Callable[[Path, Path, str, Path, str | None], dict]
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


def _is_red(test: str, failed: list[str]) -> bool:
    """True when `test` (an id or a file) failed itself, through its file, or through a test inside it."""
    return test in failed or test.split("::")[0] in failed or any(f.startswith(test + "::") for f in failed)


def _red_run(state: dict, ctx: Ctx) -> tuple[str, dict, dict]:
    """Run qa's added tests; `expected` when all fail and qa's reason is expected, else `unexpected`."""
    qa = _result(state, "qa_write")
    added = qa["tests_added"]
    failed = ctx.tests(ctx.repo, added)["failed"]
    red = {"tests": added, "failed": failed, "claimed": qa["red_run"]}
    (ctx.run / "red.json").write_text(json.dumps(red))
    covered = bool(added) and all(_is_red(t, failed) for t in added)
    return ("expected" if covered and qa["red_run"]["reason_expected"] else "unexpected"), red, state


def _verify(state: dict, ctx: Ctx) -> tuple[str, dict, dict]:
    """Give `tests_touched`, `fail` (stray failure, failing added test or dispute), or the unit's lane."""
    unit = (ctx.run / "unit.md").read_text()
    touched = ctx.touched(ctx.repo)
    disputed = _result(state, "implement").get("tests_disputed", [])
    entry = {"failed": [], "disputed": disputed, "touched": touched}
    if touched:
        return "tests_touched", entry, state
    entry["failed"] = ctx.tests(ctx.repo, [])["failed"]
    added = _result(state, "qa_write")["tests_added"]
    stray = [f for f in entry["failed"] if f not in units.declared_breaks(unit)]
    hit = [f for f in entry["failed"] if f in added or f.split("::")[0] in added]
    return ("fail" if stray or hit or disputed else units.unit_lane(unit)), entry, state


def _made_already(state: dict, ctx: Ctx, message: str) -> str | None:
    """Return HEAD's sha when HEAD is this message's commit, made by a run that died before saving the state.

    None while the working tree has uncommitted changes, or when the state already holds HEAD.
    """
    shown = ctx.source(ctx.repo, "HEAD", None).splitlines()
    subject = next((line.strip() for line in shown if line.startswith("    ")), "")
    sha = shown[0].split()[1]
    resumable = subject == message.splitlines()[0] and sha != state["head"] and not ctx.diff(ctx.repo).strip()
    return sha if resumable else None


def _commit(state: dict, ctx: Ctx, message: str, paths: list[str] | None) -> tuple[str, dict, dict]:
    try:
        sha = ctx.commit(ctx.repo, message, paths)
    except RuntimeError as err:
        sha = _made_already(state, ctx, message)
        if sha is None:
            return "refused", {"message": message, "error": str(err)}, state
    ctx.log(ctx.run, [sha, message])
    return "done", {"sha": sha, "message": message}, {**state, "head": sha}


def _commit_tests(state: dict, ctx: Ctx) -> tuple[str, dict, dict]:
    """Commit only the touched test paths and start their `tests` review; `refused` if none or a hook fails."""
    message = units.test_commit_message((ctx.run / "unit.md").read_text())
    paths = ctx.touched(ctx.repo)
    if not paths:
        return "refused", {"message": message, "error": "no test paths to commit"}, state
    outcome, entry, new = _commit(state, ctx, message, paths)
    if outcome == "done":
        args = review.review_args("tests", ctx.run, state["plan"], entry["sha"], None)
        new = {**new, "review": ctx.start_review(args, ctx.repo, ctx.run / f"review-tests-{entry['sha']}.log")}
    return outcome, entry, new


def _commit_all(state: dict, ctx: Ctx, message: str, tests_commit: str | None) -> tuple[str, dict, dict]:
    outcome, entry, new = _commit(state, ctx, message, None)
    if outcome == "done":
        path = ctx.run / f"evidence-{entry['sha']}.json"
        path.write_text(json.dumps(ctx.evidence(ctx.repo, ctx.run, entry["sha"], ctx.python, tests_commit)))
        entry = {**entry, "evidence": str(path)}
    return outcome, entry, new


def _commit_fix(state: dict, ctx: Ctx) -> tuple[str, dict, dict]:
    """Commit everything with the unit's message and record its evidence; `refused` with the error if a hook fails."""
    done = (e for e in st.unit_history(state) if e.get("node") == "commit_tests" and e.get("outcome") == "done")
    first = next((e["sha"] for e in done), None)
    return _commit_all(state, ctx, units.commit_message((ctx.run / "unit.md").read_text()), first)


def _subtract_check(state: dict, ctx: Ctx) -> tuple[str, dict, dict]:
    """Give `nothing` without edits, `fail` when tests were touched or the suite fails, else `pass`."""
    if not ctx.diff(ctx.repo).strip():
        return "nothing", {}, state
    touched = ctx.touched(ctx.repo)
    failed = [] if touched else ctx.tests(ctx.repo, [])["failed"]
    return ("fail" if touched or failed else "pass"), {"touched": touched, "failed": failed}, state


def _full_suite(state: dict, ctx: Ctx) -> tuple[str, dict, dict]:
    """Run the whole suite, accepting no declared breaks: `pass` when nothing fails, else `fail`."""
    failed = ctx.tests(ctx.repo, [])["failed"]
    return ("fail" if failed else "pass"), {"failed": failed}, state


def _commit_subtract(state: dict, ctx: Ctx) -> tuple[str, dict, dict]:
    """Commit everything as `<stories>: Subtract: <summary>` and record evidence; `refused` if a hook fails."""
    stories = units.commit_message((ctx.run / "unit.md").read_text()).split(": ", 1)[0]
    return _commit_all(state, ctx, f"{stories}: Subtract: {_result(state, 'subtract')['removed']}", None)


def _scope(state: dict) -> tuple[str | None, str | None]:
    base = state["launch"] if state["node"] in ("branch_reviews", "answers_ask") else None
    return (None if base else state["head"]), base


def _judge(name: str, path: Path | None, state: dict, ctx: Ctx) -> dict:
    """Derive one pass's verdict from its saved review; a None path is MALFORMED."""
    if path is None:
        return {"pass": name, "review": None, "verdict": "MALFORMED", "fails": [], "dropped": []}
    source = ctx.source(ctx.repo, *_scope(state))
    text = path.read_text()
    verdict, fails = review.derive_verdict(text, review.expected_ids(name, ctx.repo), source)
    dropped = [] if verdict == "MALFORMED" else review.dropped_fails(text, source)
    return {"pass": name, "review": str(path), "verdict": verdict, "fails": fails, "dropped": dropped}


def _pass_reviews(name: str, state: dict, ctx: Ctx) -> list[dict]:
    """Return the pass's reviews: the first, plus a foreground rerun if it was MALFORMED."""
    args = review.review_args(name, ctx.run, state["plan"], *_scope(state))
    collected = state["node"] == "tests_review"
    path = ctx.collect_review(state["review"]) if collected else ctx.run_review(args, ctx.repo)
    first = _judge(name, path, state, ctx)
    if first["verdict"] != "MALFORMED":
        return [first]
    return [first, _judge(name, ctx.run_review(args, ctx.repo), state, ctx)]


def _decided_since_tests_commit(state: dict) -> bool:
    nodes = [e.get("node") for e in st.unit_history(state)]
    last = max((i for i, n in enumerate(nodes) if n == "commit_tests"), default=-1)
    return "tests_decide" in nodes[last + 1 :]


def _review(state: dict, ctx: Ctx) -> tuple[str, dict, dict]:
    """Judge each of the node's review passes; outcome MALFORMED, else CHANGES if any pass has FAILs, else PASS.

    A `tests_review` already decided since the unit's latest test commit gives PASS without a review.
    """
    if state["node"] == "tests_review" and _decided_since_tests_commit(state):
        return "PASS", {"verdict": "PASS", "reviews": [], "decided": True}, state
    per_pass = [_pass_reviews(name, state, ctx) for name in graph.REVIEW_PASSES[state["node"]]]
    finals = {rs[-1]["verdict"] for rs in per_pass}
    outcome = next(v for v in ("MALFORMED", "CHANGES") if v in finals) if finals - {"PASS"} else "PASS"
    return outcome, {"verdict": outcome, "reviews": [r for rs in per_pass for r in rs]}, state


HANDLERS: dict[str, Handler] = {
    "write_unit": _write_unit,
    "next_unit": _next_unit,
    "red_run": _red_run,
    "verify": _verify,
    "commit_tests": _commit_tests,
    "commit_fix": _commit_fix,
    "commit_subtract": _commit_subtract,
    "subtract_check": _subtract_check,
    "full_suite": _full_suite,
    "tests_review": _review,
    "impl_review": _review,
    "branch_reviews": _review,
    "answers_ask": _review,
}
