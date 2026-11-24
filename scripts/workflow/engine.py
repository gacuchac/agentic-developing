"""Pure engine of the unit loop: moves the state between nodes."""

from __future__ import annotations

from pathlib import Path

import agent_steps
import contracts
import decisions
import graph
import state as st
from autonodes import HANDLERS, Ctx
from evidence import check_evidence


def _pending(state: dict, node: str, reason: str) -> dict:
    """Return the pending step that the kind of `node` requires."""
    kind = graph.kind(node)
    if kind == "agent":
        agent, step = graph.AGENT_STEPS[node]
        attempt = 1 + sum(1 for e in st.unit_history(state) if e.get("node") == node)
        return {"kind": kind, "agent": agent, "step": step, "step_id": f"u{st.unit_label(state)}-{step}-{attempt}"}
    if kind == "user":
        prev = state["node"]
        resume = sorted(set(graph.EDGES[prev].values()) - {"user"} | {prev})
        return {"kind": kind, "from": prev, "reason": reason, "resume": resume}
    return {"kind": kind}


def enter(state: dict, node: str, reason: str = "") -> dict:
    """Return a copy of state at `node`, with its round and the pending step its kind requires.

    The round is the back rounds of the unit toward `node` plus one. Entering `subtract` sets stage "finish".
    A pending agent step's id ends with its attempt at that node in the unit.
    The input state is not mutated.
    """
    round_ = graph.back_rounds(st.unit_history(state), node) + 1
    out = {**state, "node": node, "round": round_, "pending": _pending(state, node, reason)}
    return {**out, "stage": "finish"} if node == "subtract" else out


def advance(state: dict, ctx: Ctx, handlers: dict = HANDLERS) -> dict:
    """Return the state after running auto nodes through `handlers` until the node is not auto.

    Each step appends {"node", "outcome", **entry, "to"} to the history and enters the target of
    EDGES. A back edge whose target already has ROUND_CAP rounds goes to `user` with a reason.
    The input state is not mutated.
    """
    while graph.kind(state["node"]) == "auto":
        node = state["node"]
        outcome, entry, state = handlers[node](state, ctx)
        target, reason = graph.EDGES[node][outcome], ""
        if (node, outcome) in graph.BACK_EDGES and graph.back_rounds(st.unit_history(state), target) >= graph.ROUND_CAP:
            target, reason = "user", f"{node} {outcome} reached {graph.ROUND_CAP} rounds"
        logged = {"node": node, "outcome": outcome, **entry, "to": target}
        state = st.with_entry(enter(state, target, reason), logged, ctx.now())
    return state


def _last(history: list[dict], key: str) -> dict:
    return next((e for e in reversed(history) if key in e), {})


def _finding_facts(history: list[dict]) -> dict:
    passes = {i: r["pass"] for r in _last(history, "reviews").get("reviews", []) for i in r["fails"]}
    spent = {p for p, n in graph.wrong_dismissals(history).items() if n >= graph.WRONG_CAP}
    return {"fails": list(passes), "passes": passes, "capped": [i for i, p in passes.items() if p in spent]}


def _failures(state: dict, history: list[dict]) -> list[str]:
    entry = _last(history, "failed")
    disputed = [d.split(": ", 1)[0] for d in entry.get("disputed", [])]
    extra = {"fail_decide": disputed, "red_decide": entry.get("tests", [])}
    return [*entry.get("failed", []), *extra.get(state["node"], [])]


def _docs(state: dict, run: Path) -> list[str]:
    return [(run / n).read_text() for n in (state["plan"], "ask.md") if (run / n).is_file()]


def decision_facts(state: dict, ctx: Ctx) -> dict:
    """Return the facts `evidence.check_evidence` reads, built from the unit's history and the run folder.

    Keys: fails, passes (id to pass) and capped from the last review entry; failures (last run entry's
    failed, plus the test id of each disputed entry at fail_decide, or tests at red_decide); docs (plan and ask.md
    texts); read (path to text, at state["head"] at tests_decide, else the working tree); run; resume; uncovered.
    """
    history = st.unit_history(state)
    sha = state["head"] if state["node"] == "tests_decide" else None
    arch = ctx.run / "architecture.md"
    uncovered = contracts.uncovered(
        contracts.changed_signatures(ctx.diff(ctx.repo)), arch.read_text() if arch.is_file() else ""
    )
    return {
        **_finding_facts(history),
        "failures": _failures(state, history),
        "docs": _docs(state, ctx.run),
        "read": lambda path: ctx.file_at(ctx.repo, path, sha),
        "run": ctx.run,
        "resume": state["pending"].get("resume", []),
        "uncovered": uncovered,
    }


def legal(state: dict, ctx: Ctx) -> list[str]:
    """Return the options the current node offers, from `graph.legal_options` and the decision facts."""
    return graph.legal_options(state["node"], st.unit_history(state), decision_facts(state, ctx)["uncovered"])


def _refusal(state: dict, option: str, ctx: Ctx) -> list[str]:
    kind = state["pending"]["kind"]
    if kind not in ("decide", "user"):
        return [f"no decision is pending (pending is {kind})"]
    options = legal(state, ctx)
    return [] if option in options else [f"{option} is not legal at {state['node']}; legal: {', '.join(options)}"]


def _entry(state: dict, option: str, evidence: dict, facts: dict) -> dict:
    node = state["node"]
    entry = {"node": node, "decision": option, "evidence": evidence}
    if option == "user_continue":
        return {**entry, "to": evidence["to"], "by": "user"}
    to = graph.EDGES[node].get(option, graph.STOPS.get(option))
    if option in ("overstated", "wrong"):
        entry["passes"] = {f["id"]: facts["passes"][f["id"]] for f in evidence["findings"]}
        to = node if graph.undismissed([*st.unit_history(state), entry], node, facts["fails"]) else to
    return {**entry, "to": to}


def take(state: dict, option: str, evidence: dict, ctx: Ctx, handlers: dict = HANDLERS) -> tuple[dict, list[str]]:
    """Record the decision `option` with its `evidence`, enter the target node and advance.

    Returns (new state, []) when accepted. Returns (state unchanged, errors) when the pending step is
    not decide or user, the option is not in `legal`, or `check_evidence` finds errors.
    Appends {"node", "decision", "evidence", "to"} to the history, plus "passes" for overstated and wrong
    (the task stays at the node while findings are undismissed) and "by": "user" for user_continue.
    A target of write_unit raises `fix` by 1. Calls ctx.log once per accepted decision.
    """
    facts = decision_facts(state, ctx)
    errors = _refusal(state, option, ctx) or check_evidence(option, evidence, facts)
    if errors:
        return state, errors
    entry = _entry(state, option, evidence, facts)
    out = st.with_entry(state, entry, ctx.now())
    ctx.log(ctx.run, decisions.row(out["history"][-1]))
    out = {**out, "fix": out["fix"] + (entry["to"] == "write_unit")}
    reason = str(evidence.get("question", evidence.get("path", "")))
    return advance(enter(out, entry["to"], reason), ctx, handlers), []


def _record_errors(state: dict, step_id: str, result: dict) -> list[str]:
    pending = state["pending"]
    if pending["kind"] != "agent" or pending["step_id"] != step_id:
        return [f"no agent step {step_id} is pending"]
    return agent_steps.validate_result(agent_steps.RESULT_KEYS[pending["step"]], result)


def record(state: dict, step_id: str, result: dict, ctx: Ctx, handlers: dict = HANDLERS) -> tuple[dict, list[str]]:
    """Record an agent's `result` for the pending step `step_id`, enter the recorded target and advance.

    Returns (new state, []) when accepted. Returns (state unchanged, errors) when the pending step is
    not the agent step `step_id` or `agent_steps.validate_result` finds errors in the result.
    Appends {"node", "result", "to"} to the history, where to is EDGES[node]["recorded"].
    """
    errors = _record_errors(state, step_id, result)
    if errors:
        return state, errors
    node = state["node"]
    target = graph.EDGES[node]["recorded"]
    out = st.with_entry(state, {"node": node, "result": result, "to": target}, ctx.now())
    return advance(enter(out, target), ctx, handlers), []
