"""Pure engine of the unit loop: moves the state between nodes."""
from __future__ import annotations

import graph
import state as st
from autonodes import HANDLERS, Ctx


def _pending(state: dict, node: str, round_: int, reason: str) -> dict:
    """Return the pending step that the kind of `node` requires."""
    kind = graph.kind(node)
    if kind == "agent":
        agent, step = graph.AGENT_STEPS[node]
        return {"kind": kind, "agent": agent, "step": step, "step_id": f"u{st.unit_label(state)}-{step}-{round_}"}
    if kind == "user":
        prev = state["node"]
        resume = sorted(set(graph.EDGES[prev].values()) - {"user"} | {prev})
        return {"kind": kind, "from": prev, "reason": reason, "resume": resume}
    return {"kind": kind}


def enter(state: dict, node: str, reason: str = "") -> dict:
    """Return a copy of state at `node`, with its round and the pending step its kind requires.

    The round is the back rounds of the unit toward `node` plus one. Entering `subtract` sets stage "finish".
    The input state is not mutated.
    """
    round_ = graph.back_rounds(st.unit_history(state), node) + 1
    out = {**state, "node": node, "round": round_, "pending": _pending(state, node, round_, reason)}
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
