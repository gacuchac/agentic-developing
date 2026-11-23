"""Tests for scripts/workflow/graph.py: the edges of the unit loop (US-7)."""

import graph

EDGES = graph.EDGES


def test_us7_every_target_is_a_node():
    for node, edges in EDGES.items():
        for outcome, target in edges.items():
            assert target in EDGES, f"{node} --{outcome}--> {target}"


def test_us7_escalate_comes_with_architecture_stop():
    for node, edges in EDGES.items():
        if "escalate" in edges:
            assert "architecture_stop" in edges, node


def test_us7_every_node_reachable_from_write_unit():
    seen, todo = set(), ["write_unit"]
    while todo:
        n = todo.pop()
        if n in seen:
            continue
        seen.add(n)
        todo.extend(EDGES[n].values())
    assert seen == set(EDGES)


def test_us7_count_lines_ok_commits_and_commit_done_goes_to_reviews():
    assert EDGES["count_lines"]["ok"] == "commit"
    assert EDGES["commit"]["done"] == "commit_reviews"


def test_us7_stops_go_to_user():
    assert graph.STOPS == {"escalate": "user", "architecture_stop": "user"}


def test_us7_red_run_edges():
    assert EDGES["red_run"] == {"expected": "tests_review", "unexpected": "red_decide"}


def test_us7_run_tests_fail_goes_to_fail_decide():
    assert EDGES["run_tests"]["pass"] == "count_lines"
    assert EDGES["run_tests"]["fail"] == "fail_decide"


def test_us7_fail_decide_code_wrong_implements_tests_wrong_rewrites():
    assert EDGES["fail_decide"]["code_wrong"] == "implement"
    assert EDGES["fail_decide"]["tests_wrong"] == "qa_write"


def test_us7_commit_reviews_changes_goes_to_commit_decide():
    assert EDGES["commit_reviews"]["CHANGES"] == "commit_decide"
    assert EDGES["commit_reviews"]["PASS"] == "next_unit"
    assert EDGES["commit_reviews"]["MALFORMED"] == "user"


def test_us7_next_unit_last_goes_to_full_suite():
    assert EDGES["next_unit"] == {"more": "write_unit", "last": "full_suite"}


def test_us7_commit_refused_stalls_on_commit():
    assert EDGES["commit"]["refused"] == "commit"


def test_us7_count_lines_over_returns_to_implement():
    assert EDGES["count_lines"]["over"] == "implement"


def test_us7_review_decisions_dismissed_skip_ahead():
    assert EDGES["tests_decide"]["wrong"] == "implement"
    assert EDGES["impl_decide"]["wrong"] == "run_tests"
    assert EDGES["commit_decide"]["wrong"] == "next_unit"
    assert EDGES["aa_decide"]["wrong"] == "done"


def test_us7_user_and_done_have_no_edges():
    assert EDGES["user"] == {}
    assert EDGES["done"] == {}


def test_us7_edges_match_the_unit_loop_table():
    expected = {
        "write_unit": {"done": "qa_write"},
        "qa_write": {"recorded": "red_run"},
        "red_run": {"expected": "tests_review", "unexpected": "red_decide"},
        "red_decide": {"tests_wrong": "qa_write"},
        "tests_review": {
            "PASS": "implement",
            "CHANGES": "tests_decide",
            "MALFORMED": "user",
        },
        "tests_decide": {
            "correct": "qa_write",
            "overstated": "implement",
            "wrong": "implement",
        },
        "implement": {"recorded": "impl_review"},
        "impl_review": {
            "PASS": "run_tests",
            "CHANGES": "impl_decide",
            "MALFORMED": "user",
        },
        "impl_decide": {
            "correct": "implement",
            "overstated": "run_tests",
            "wrong": "run_tests",
        },
        "run_tests": {"pass": "count_lines", "fail": "fail_decide"},
        "fail_decide": {"code_wrong": "implement", "tests_wrong": "qa_write"},
        "count_lines": {"ok": "commit", "over": "implement"},
        "commit": {"done": "commit_reviews", "refused": "commit"},
        "commit_reviews": {
            "PASS": "next_unit",
            "CHANGES": "commit_decide",
            "MALFORMED": "user",
        },
        "commit_decide": {
            "correct": "write_unit",
            "overstated": "next_unit",
            "wrong": "next_unit",
        },
        "next_unit": {"more": "write_unit", "last": "full_suite"},
        "full_suite": {"pass": "answers_ask", "fail": "full_decide"},
        "full_decide": {"code_wrong": "write_unit"},
        "answers_ask": {
            "PASS": "done",
            "CHANGES": "aa_decide",
            "MALFORMED": "user",
        },
        "aa_decide": {
            "correct": "write_unit",
            "overstated": "done",
            "wrong": "done",
        },
        "user": {},
        "done": {},
    }
    for node in expected:
        if node.endswith("_decide"):
            expected[node] = {**expected[node], **graph.STOPS}
    assert graph.EDGES == expected


def test_us7_agent_steps_exact():
    assert graph.AGENT_STEPS == {
        "qa_write": ("qa", "write"),
        "implement": ("implementer", "code"),
    }


def test_us7_review_passes_exact():
    assert graph.REVIEW_PASSES == {
        "tests_review": ("tests",),
        "impl_review": ("impl",),
        "commit_reviews": ("commit", "principles", "alternatives"),
        "answers_ask": ("answers-ask",),
    }


def test_us7_decides_on_exact():
    assert graph.DECIDES_ON == {
        "tests_decide": "tests_review",
        "impl_decide": "impl_review",
        "commit_decide": "commit_reviews",
        "aa_decide": "answers_ask",
    }


def test_us7_back_edges_exact_with_targets():
    assert graph.BACK_EDGES == {
        ("tests_decide", "correct"): "qa_write",
        ("red_decide", "tests_wrong"): "qa_write",
        ("impl_decide", "correct"): "implement",
        ("fail_decide", "code_wrong"): "implement",
        ("fail_decide", "tests_wrong"): "qa_write",
        ("count_lines", "over"): "implement",
    }


def test_us7_caps():
    assert graph.ROUND_CAP == 3
    assert graph.WRONG_CAP == 2


def test_us7_kind_of_every_node():
    agent = {"qa_write", "implement"}
    decide = {
        "red_decide", "tests_decide", "impl_decide", "fail_decide",
        "commit_decide", "full_decide", "aa_decide",
    }
    auto = {
        "write_unit", "red_run", "tests_review", "impl_review", "run_tests",
        "count_lines", "commit", "commit_reviews", "next_unit", "full_suite",
        "answers_ask",
    }
    expected = {n: "agent" for n in agent}
    expected.update({n: "decide" for n in decide})
    expected.update({n: "auto" for n in auto})
    expected.update({"user": "user", "done": "end"})
    assert {n: graph.kind(n) for n in EDGES} == expected


def test_us7_commit_is_auto():
    assert graph.kind("commit") == "auto"


def test_us7_back_edges_are_real_edges():
    for (node, outcome), target in graph.BACK_EDGES.items():
        assert EDGES[node][outcome] == target


def test_us7_decides_on_values_are_review_passes():
    for decide, review in graph.DECIDES_ON.items():
        assert review in graph.REVIEW_PASSES, decide
