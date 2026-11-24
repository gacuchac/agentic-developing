"""Plain-text views of a task's state and of its decision log."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import time
from collections import Counter
from collections.abc import Mapping
from functools import partial
from pathlib import Path

import agent_steps
import claims
import decisions
import engine
import graph
import state as st
import units
from autonodes import Ctx
from effects import checks, claimfiles, gitops, procs, reviews

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


def dropped_text(state: dict) -> str:
    """Return a `dropped: <pass> <ids> (<review file name>)` line per history review that dropped a FAIL; "" if none."""
    return "\n".join(
        f"dropped: {r['pass']} {' '.join(r['dropped'])} ({Path(r['review']).name})"
        for e in state.get("history", [])
        for r in e.get("reviews", [])
        if r.get("dropped")
    )


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
        collect_review=partial(reviews.collect_pass, timeout=1800),
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


def identity(env: Mapping[str, str]) -> tuple[str, int]:
    """Return (CLAUDE_CODE_SESSION_ID, int(CLAUDE_PID)) from env; ("", 0) when either is missing."""
    session, pid = env.get("CLAUDE_CODE_SESSION_ID", ""), env.get("CLAUDE_PID", "")
    return (session, int(pid)) if session and pid.isdigit() else ("", 0)


def _log_takeover(run: Path, ctx: Ctx, message: str) -> None:
    ctx.log(run, [ctx.now(), "takeover", "takeover", message, "", ""])


def run_release(run: Path, reason: str, env: Mapping[str, str], ctx: Ctx) -> list[str]:
    """Release the run's claim and log a release row with the reason and old holder; return [] or error lines.

    Refuses with one error line, leaving the claim, when env has WF_AGENT=1 (a workflow subagent).
    """
    if env.get("WF_AGENT") == "1":
        return ["wf release is for the user, not for workflow agents"]
    held = claims.release(run.parents[1] / ".active", claims.claim_name(run.parent.name, run.name))
    ctx.log(run, [ctx.now(), "release", "release", reason, (held or {}).get("session", ""), ""])
    return []


def run_claim(run: Path, env: Mapping[str, str], ctx: Ctx) -> list[str]:
    """Claim the run's task for the session in env; return [] or one error line naming the live holder.

    With an empty identity no claim is made and [] is returned.
    """
    session, pid = identity(env)
    if not session:
        return []
    branch, _ = gitops.launch_info(ctx.repo)
    claim = claims.make_claim(session, pid, procs.pid_start(pid) or "", str(run), str(ctx.repo), branch, ctx.now())
    name = claims.claim_name(run.parent.name, run.name)
    log = partial(_log_takeover, run, ctx)
    outcome, holder = claims.acquire(run.parents[1] / ".active", name, claim, procs.pid_alive, procs.pid_start, log)
    if outcome != "refused":
        return []
    return [f"{name} is held by session {holder['session']} on {holder['branch']} since {holder['since']}"]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wf")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("start", "status", "options", "report", "take", "record"):
        sub.add_parser(name).add_argument("run", type=Path)
    sub.add_parser("release").add_argument("run", type=Path)
    sub.choices["release"].add_argument("--reason", required=True)
    sub.choices["start"].add_argument("--plan", default="plan.md")
    sub.choices["take"].add_argument("option")
    sub.choices["take"].add_argument("--evidence", type=Path)
    sub.choices["record"].add_argument("step_id")
    sub.choices["record"].add_argument("result", type=Path)
    return parser


def _run(args: argparse.Namespace, ctx: Ctx) -> tuple[dict | None, list[str]]:
    run = args.run
    if args.cmd == "start":
        return start_state(run, args.plan, ctx)
    state = st.load(run)
    if args.cmd == "take":
        evidence = json.loads(args.evidence.read_text()) if args.evidence else {}
        return engine.take(state, args.option, evidence, ctx)
    return engine.record(state, args.step_id, json.loads(args.result.read_text()), ctx)


def _holder_line(run: Path) -> str:
    name = claims.claim_name(run.parent.name, run.name)
    holder = claimfiles.read(run.parents[1] / ".active", name)
    return f"held by: {holder['session']} on {holder['branch']} since {holder['since']}" if holder else "held by: -"


def root_warning(root_branch: str, task_is_root: bool) -> str | None:
    """Return a one-line warning when a project task sees the workspace root off dev; None otherwise."""
    if task_is_root or root_branch == "dev":
        return None
    return f"warning: the workspace root is on '{root_branch}', not dev; switch the root back to dev"


def _show(args: argparse.Namespace, ctx: Ctx) -> None:
    if args.cmd == "status":
        state = st.load(args.run)
        print(status_text(state))
        if dropped_text(state):
            print(dropped_text(state))
        print(_holder_line(args.run))
        workspace = args.run.parents[3]
        branch = gitops.current_branch(workspace)
        warning = None if branch is None else root_warning(branch, repo_for(args.run) == workspace)
        if warning:
            print(warning)
    elif args.cmd == "options":
        print(json.dumps(options_view(st.load(args.run), ctx), indent=2))
    else:
        log = args.run / "decisions.tsv"
        print(report_text(log.read_text() if log.is_file() else ""))
        print("## Dropped findings\n" + dropped_text(st.load(args.run)))


def main(argv: list[str] | None = None) -> int:
    """Run one wf command; return 0; 2 when another session holds the task; 1 on refusal errors (printed to stderr)."""
    args = _parser().parse_args(argv)
    ctx = default_ctx(args.run)
    if args.cmd == "release":
        errors = run_release(args.run, args.reason, os.environ, ctx)
        if errors:
            print("\n".join(errors), file=sys.stderr)
        return 1 if errors else 0
    if args.cmd not in ("start", "take", "record"):
        _show(args, ctx)
        return 0
    errors = run_claim(args.run, os.environ, ctx)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 2
    state, errors = _run(args, ctx)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    st.save(args.run, state)
    print(status_text(state))
    return 0


if __name__ == "__main__":
    sys.exit(main())
