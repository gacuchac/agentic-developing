"""Edges of the unit loop: node to outcome-or-option to target node."""

STOPS = {"escalate": "user", "architecture_stop": "user"}

_RAW: dict[str, dict[str, str]] = {
    "write_unit": {"done": "qa_write"},
    "qa_write": {"recorded": "red_run"},
    "red_run": {"expected": "tests_review", "unexpected": "red_decide"},
    "red_decide": {"tests_wrong": "qa_write"},
    "tests_review": {"PASS": "implement", "CHANGES": "tests_decide", "MALFORMED": "user"},
    "tests_decide": {"correct": "qa_write", "overstated": "implement", "wrong": "implement"},
    "implement": {"recorded": "impl_review"},
    "impl_review": {"PASS": "run_tests", "CHANGES": "impl_decide", "MALFORMED": "user"},
    "impl_decide": {"correct": "implement", "overstated": "run_tests", "wrong": "run_tests"},
    "run_tests": {"pass": "count_lines", "fail": "fail_decide"},
    "fail_decide": {"code_wrong": "implement", "tests_wrong": "qa_write"},
    "count_lines": {"ok": "commit", "over": "implement"},
    "commit": {"done": "commit_reviews", "refused": "commit"},
    "commit_reviews": {"PASS": "next_unit", "CHANGES": "commit_decide", "MALFORMED": "user"},
    "commit_decide": {"correct": "write_unit", "overstated": "next_unit", "wrong": "next_unit"},
    "next_unit": {"more": "write_unit", "last": "full_suite"},
    "full_suite": {"pass": "answers_ask", "fail": "full_decide"},
    "full_decide": {"code_wrong": "write_unit"},
    "answers_ask": {"PASS": "done", "CHANGES": "aa_decide", "MALFORMED": "user"},
    "aa_decide": {"correct": "write_unit", "overstated": "done", "wrong": "done"},
    "user": {},
    "done": {},
}

EDGES: dict[str, dict[str, str]] = {n: {**e, **STOPS} if n.endswith("_decide") else e for n, e in _RAW.items()}

AGENT_STEPS = {"qa_write": ("qa", "write"), "implement": ("implementer", "code")}
REVIEW_PASSES = {
    "tests_review": ("tests",),
    "impl_review": ("impl",),
    "commit_reviews": ("commit", "principles", "alternatives"),
    "answers_ask": ("answers-ask",),
}
DECIDES_ON = {
    "tests_decide": "tests_review",
    "impl_decide": "impl_review",
    "commit_decide": "commit_reviews",
    "aa_decide": "answers_ask",
}
_BACK = [("tests_decide", "correct"), ("red_decide", "tests_wrong"), ("impl_decide", "correct")]
_BACK += [("fail_decide", "code_wrong"), ("fail_decide", "tests_wrong"), ("count_lines", "over")]
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
