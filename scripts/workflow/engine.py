"""Pure engine of the unit loop: moves the state between nodes."""
from __future__ import annotations

import graph
import state as st


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
