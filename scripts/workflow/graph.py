"""Edges of the unit loop: node to outcome-or-option to target node."""

STOPS = {"escalate": "user", "architecture_stop": "user"}

_RAW: dict[str, dict[str, str]] = {
    "write_unit": {"done": "qa_write"},
    "qa_write": {"recorded": "red_run"},
    "red_run": {"expected": "commit_tests", "unexpected": "red_decide"},
    "red_decide": {"tests_wrong": "qa_write"},
    "commit_tests": {"done": "implement", "refused": "qa_write"},
    "implement": {"recorded": "tests_review"},
    "tests_review": {"PASS": "verify", "CHANGES": "tests_decide", "MALFORMED": "user"},
    "tests_decide": {"correct": "qa_fix", "overstated": "verify", "wrong": "verify"},
    "qa_fix": {"recorded": "commit_tests"},
    "verify": {"fast": "commit_fix", "full": "impl_review", "tests_touched": "implement", "fail": "fail_decide"},
    "fail_decide": {"code_wrong": "implement", "tests_wrong": "qa_fix"},
    "impl_review": {"PASS": "commit_fix", "CHANGES": "impl_decide", "MALFORMED": "user"},
    "impl_decide": {"correct": "implement", "overstated": "commit_fix", "wrong": "commit_fix"},
    "commit_fix": {"done": "next_unit", "refused": "implement"},
    "next_unit": {"more": "write_unit", "last": "done", "finished": "done"},
    "full_suite": {"pass": "answers_ask", "fail": "full_decide"},
    "full_decide": {"code_wrong": "write_unit"},
    "answers_ask": {"PASS": "done", "CHANGES": "aa_decide", "MALFORMED": "user"},
    "aa_decide": {"correct": "write_unit", "overstated": "done", "wrong": "done"},
    "user": {},
    "done": {},
}

EDGES: dict[str, dict[str, str]] = {n: {**e, **STOPS} if n.endswith("_decide") else e for n, e in _RAW.items()}

AGENT_STEPS = {"qa_write": ("qa", "write"), "qa_fix": ("qa", "fix"), "implement": ("implementer", "code")}
REVIEW_PASSES = {
    "tests_review": ("tests",),
    "impl_review": ("impl",),
    "answers_ask": ("answers-ask",),
}
DECIDES_ON = {
    "tests_decide": "tests_review",
    "impl_decide": "impl_review",
    "aa_decide": "answers_ask",
}
_BACK = [("tests_decide", "correct"), ("red_decide", "tests_wrong"), ("impl_decide", "correct")]
_BACK += [("fail_decide", "code_wrong"), ("fail_decide", "tests_wrong"), ("verify", "tests_touched")]
_BACK += [("commit_tests", "refused"), ("commit_fix", "refused")]
BACK_EDGES: dict[tuple[str, str], str] = {(n, o): EDGES[n][o] for n, o in _BACK}
ROUND_CAP = 3
WRONG_CAP = 2


def kind(node: str) -> str:
    """Return "agent", "decide", "user", "end" or "auto" for a node of EDGES."""
    if node in AGENT_STEPS:
        return "agent"
    if "escalate" in EDGES[node]:
        return "decide"
    return {"user": "user", "done": "end"}.get(node, "auto")


def back_rounds(entries: list[dict], target: str) -> int:
    """Count back-edge entries going to `target` after the last user_continue entry; input is not mutated."""
    start = max(
        (i + 1 for i, e in enumerate(entries) if "user_continue" in (e.get("decision"), e.get("outcome"))), default=0
    )
    return sum(
        1
        for e in entries[start:]
        if (e.get("node"), e.get("decision") or e.get("outcome")) in BACK_EDGES and e.get("to") == target
    )


def cap_reached(entries: list[dict], node: str) -> bool:
    """Return True when any back edge leaving `node` has reached ROUND_CAP rounds in `entries`."""
    return any(back_rounds(entries, t) >= ROUND_CAP for (n, _), t in BACK_EDGES.items() if n == node)


def wrong_dismissals(entries: list[dict]) -> dict[str, int]:
    """Count per pass the finding ids dismissed as "wrong" in decision entries; input is not mutated.

    Reads, from each entry with `decision == "wrong"`: `evidence["findings"]` (the dismissed
    finding ids) and `passes`, a mapping finding id -> review pass. Other entries are ignored.
    """
    counts: dict[str, int] = {}
    for e in entries:
        if e.get("decision") == "wrong":
            for i in e["evidence"]["findings"]:
                p = e["passes"][i]
                counts[p] = counts.get(p, 0) + 1
    return counts


def undismissed(entries: list[dict], node: str, fails: list[str]) -> list[str]:
    """Return the ids in `fails`, in order, not dismissed (wrong or overstated) at `node` since the last review entry.

    A review entry is any entry with a `"reviews"` key; only entries after the last one count.
    Reads from those: `node`, `decision` (in "wrong" or "overstated") and `evidence["findings"]`.
    """
    start = max((i + 1 for i, e in enumerate(entries) if "reviews" in e), default=0)
    gone = {
        f
        for e in entries[start:]
        if e.get("node") == node and e.get("decision") in ("wrong", "overstated")
        for f in e["evidence"]["findings"]
    }
    return [f for f in fails if f not in gone]


def legal_options(node: str, entries: list[dict], uncovered: set[str]) -> list[str]:
    """Return a fresh list of the options `node` offers given the history `entries` and `uncovered` contract ids.

    Non-decide nodes: "user" gives ["user_continue"], "auto" gives list(STOPS), others give [].
    Decide nodes, first match wins: non-empty `uncovered` gives ["architecture_stop"]; cap_reached
    gives list(STOPS); else the node's edge keys, minus "wrong" once every pass of its review
    reached WRONG_CAP wrong dismissals (see wrong_dismissals). Inputs are not mutated.
    """
    k = kind(node)
    if k != "decide":
        return {"user": ["user_continue"], "auto": list(STOPS)}.get(k, [])
    if uncovered:
        return ["architecture_stop"]
    if cap_reached(entries, node):
        return list(STOPS)
    counts = wrong_dismissals(entries)
    spent = all(counts.get(p, 0) >= WRONG_CAP for p in REVIEW_PASSES[DECIDES_ON[node]]) if node in DECIDES_ON else False
    return [o for o in EDGES[node] if not (o == "wrong" and spent)]
