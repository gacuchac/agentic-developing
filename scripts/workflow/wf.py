"""Plain-text views of a task's state and of its decision log."""

from collections import Counter
from pathlib import Path

import agent_steps
from autonodes import Ctx

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
