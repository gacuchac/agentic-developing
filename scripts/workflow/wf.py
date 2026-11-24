"""Plain-text views of a task's state and of its decision log."""

from __future__ import annotations

import importlib.util
import sys
import time
from collections import Counter
from pathlib import Path

import agent_steps
import decisions
import engine
import graph
import state as st
import units
from autonodes import Ctx
from effects import checks, gitops, reviews

_EVIDENCE = {
    "correct": ["findings"],
    "overstated": ["findings"],
    "wrong": ["findings"],
    "code_wrong": ["tests"],
    "tests_wrong": ["test", "quote"],
    "escalate": ["question"],
    "architecture_stop": ["path"],
    "user_continue": ["user_said", "to"],
}


def status_text(state: dict, last: int = 5) -> str:
    """Return the task line, the pending line and the last `last` history entries of a state."""
    head = " ".join(f"{k}={state.get(k)}" for k in ("task", "mode", "stage", "unit", "node", "round"))
    pending = state.get("pending") or {}
    lines = [head, "pending: " + " ".join(f"{k}={v}" for k, v in pending.items())]
    for e in state.get("history", [])[-last:] if last > 0 else []:
        lines.append(f"{e.get('node')} {e.get('outcome')} -> {e.get('to')} {e.get('error', '')}".rstrip())
    return "\n".join(lines)


def report_text(log: str) -> str:
    """Return Decisions, Dismissals, Commits and Ratchet candidates sections for the text of decisions.tsv."""
    rows = [line.split("\t") for line in log.splitlines()[1:] if line]
    rows = [r + [""] * (6 - len(r)) for r in rows]
    dismissed = [r for r in rows if r[2] in ("overstated", "wrong")]
    ids = Counter(i for r in dismissed for i in r[4].split("; ") if i)
    sections = {
        "Decisions": rows,
        "Dismissals": dismissed,
        "Commits": [r for r in rows if "commit" in r[1]],
    }
    out = [f"## {title}\n" + "\n".join(" | ".join(r) for r in rs) for title, rs in sections.items()]
    out.append("## Ratchet candidates\n" + "\n".join(i for i, n in ids.items() if n >= 2))
    return "\n".join(out)


def repo_for(run: Path) -> Path:
    """Return the repo of a run folder: the workspace itself, or its project folder."""
    workspace = run.parents[3]
    return workspace if run.parent.name == workspace.name else workspace / run.parent.name


def _launch(state: dict, ctx: Ctx) -> dict:
    pending = state["pending"]
    agent, step, step_id = pending["agent"], pending["step"], pending["step_id"]
    file = ctx.run.parents[3] / ".claude" / "workflow" / "prompts" / f"{agent}-{step}.md"
    unit = ctx.run / "unit.md"
    prompt = agent_steps.render_prompt(
        agent,
        step,
        step_id,
        ctx.run,
        ctx.repo,
        unit.read_text() if unit.is_file() else "",
        file.read_text() if file.is_file() else None,
    )
    error = (state["history"] or [{}])[-1].get("error", "")
    return {"id": "launch", "kind": "agent", "agent": agent, "step_id": step_id, "prompt": prompt + error}


def options_view(state: dict, ctx: Ctx) -> list[dict]:
    """Return the pending step's options.

    An agent step gives one launch with its prompt; a decide or user node gives one entry per legal
    option (architecture_stop only when it is the sole one); an end gives [].
    """
    kind = state["pending"]["kind"]
    if kind == "agent":
        return [_launch(state, ctx)]
    if kind == "end":
        return []
    node, legal = state["node"], engine.legal(state, ctx)
    shown = legal if len(legal) == 1 else [o for o in legal if o != "architecture_stop"]
    return [
        {"id": o, "kind": kind, "to": graph.EDGES[node].get(o, graph.STOPS.get(o)), "evidence": _EVIDENCE[o]}
        for o in shown
    ]


def _measure() -> object:
    path = Path(__file__).resolve().parents[1] / "hooks" / "evidence_record.py"
    spec = importlib.util.spec_from_file_location("evidence_record", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.measure


def _logger(run: Path) -> object:
    def log(_run: Path, cells: list[str]) -> None:
        path = run / "decisions.tsv"
        path.write_text(decisions.append_text(path.read_text() if path.is_file() else "", cells))

    return log


def default_ctx(run: Path) -> Ctx:
    """Return the Ctx of a run folder wired to the real reviews, tests, git, evidence and decision log."""
    repo = repo_for(run)
    venv = repo / ".venv" / "bin" / "python"
    return Ctx(
        run=run,
        repo=repo,
        python=venv if venv.exists() else Path(sys.executable),
        start_review=reviews.start_pass,
        collect_review=reviews.collect_pass,
        run_review=reviews.run_pass,
        tests=checks.run_pytest,
        touched=checks.tests_touched,
        source=reviews.review_source,
        commit=gitops.commit,
        evidence=_measure(),
        diff=gitops.worktree_diff,
        file_at=gitops.file_at,
        log=_logger(run),
        now=lambda: time.strftime("%Y-%m-%dT%H:%M:%S"),
    )


def start_state(run: Path, plan: str, ctx: Ctx) -> tuple[dict | None, list[str]]:
    """Create the state of a task and advance it to its first agent step.

    Returns (state, []) on success. Returns (None, errors) when run/state.json exists, run/<plan> is
    missing or has no units, or the branch and launch commit cannot be found.
    """
    if (run / "state.json").exists():
        return None, [f"{run / 'state.json'} already exists"]
    if not (run / plan).is_file():
        return None, [f"{run / plan} is missing"]
    if not units.plan_units((run / plan).read_text()):
        return None, [f"{plan} has no units"]
    try:
        branch, launch = gitops.launch_info(ctx.repo)
    except RuntimeError as e:
        return None, [str(e).strip()]
    state = st.new_state(f"{run.parent.name}/{run.name}", branch, launch, plan)
    return engine.advance(state, ctx), []
