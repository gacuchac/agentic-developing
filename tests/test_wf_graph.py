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


def _back(node, decision, to):
    return {"node": node, "decision": decision, "to": to}


def _impl_back():
    return _back("impl_decide", "correct", "implement")


def _user_continue(to="implement"):
    return {"node": "user", "decision": "user_continue", "to": to}


def test_us7_two_back_rounds_do_not_cap_impl_decide():
    entries = [_impl_back(), _impl_back()]
    assert graph.cap_reached(entries, "impl_decide") is False


def test_us7_three_back_rounds_cap_impl_decide():
    entries = [_impl_back(), _impl_back(), _impl_back()]
    assert graph.cap_reached(entries, "impl_decide") is True


def test_us7_no_entries_means_no_cap():
    assert graph.back_rounds([], "implement") == 0
    assert graph.cap_reached([], "impl_decide") is False


def test_us7_back_rounds_returns_exact_count():
    for n in range(0, 6):
        assert graph.back_rounds([_impl_back()] * n, "implement") == n


def test_us7_forward_entries_do_not_count():
    forward = {"node": "tests_review", "outcome": "PASS", "to": "implement"}
    entries = [forward, forward, forward, _impl_back()]
    assert graph.back_rounds(entries, "implement") == 1
    assert graph.cap_reached(entries, "impl_decide") is False


def test_us7_outcome_key_back_edges_count():
    over = {"node": "count_lines", "outcome": "over", "to": "implement"}
    assert graph.back_rounds([over, over], "implement") == 2


def test_us7_user_continue_resets_the_count():
    entries = [_impl_back()] * 3 + [_user_continue()]
    assert graph.back_rounds(entries, "implement") == 0
    assert graph.cap_reached(entries, "impl_decide") is False


def test_us7_entries_after_user_continue_count():
    entries = [_impl_back()] * 3 + [_user_continue()] + [_impl_back()] * 2
    assert graph.back_rounds(entries, "implement") == 2
    assert graph.cap_reached(entries, "impl_decide") is False
    entries.append(_impl_back())
    assert graph.cap_reached(entries, "impl_decide") is True


def test_us7_only_last_user_continue_resets():
    entries = [_impl_back(), _user_continue(), _impl_back(), _impl_back(),
               _user_continue(), _impl_back()]
    assert graph.back_rounds(entries, "implement") == 1


def test_us7_count_lines_over_three_times_caps_count_lines():
    over = {"node": "count_lines", "outcome": "over", "to": "implement"}
    assert graph.cap_reached([over, over], "count_lines") is False
    assert graph.cap_reached([over, over, over], "count_lines") is True


def test_us7_rounds_to_implement_pool_across_nodes():
    entries = [
        _impl_back(),
        _back("fail_decide", "code_wrong", "implement"),
        {"node": "count_lines", "outcome": "over", "to": "implement"},
    ]
    assert graph.back_rounds(entries, "implement") == 3
    assert graph.cap_reached(entries, "impl_decide") is True


def test_us7_back_edge_to_other_target_does_not_count():
    to_qa = [_back("tests_decide", "correct", "qa_write")] * 3
    assert graph.back_rounds(to_qa, "implement") == 0
    assert graph.back_rounds(to_qa, "qa_write") == 3
    assert graph.cap_reached(to_qa, "impl_decide") is False
    assert graph.cap_reached(to_qa, "tests_decide") is True


def test_us7_cap_reached_false_for_node_without_back_edges():
    entries = [_impl_back()] * 5
    assert graph.cap_reached(entries, "commit") is False


def test_us7_cap_reached_any_back_edge_of_node_triggers():
    entries = [_back("tests_decide", "correct", "qa_write")] * 3
    assert graph.cap_reached(entries, "fail_decide") is True
    assert graph.cap_reached(entries, "red_decide") is True


def _review(node="tests_review", outcome="CHANGES"):
    return {"node": node, "outcome": outcome, "verdict": outcome,
            "reviews": [{"pass": "tests", "review": "review-tests-1.md",
                         "verdict": outcome, "fails": ["T1", "T2"]}]}


def _dismiss(decision, ids, node="tests_decide", pass_="tests"):
    return {"node": node, "decision": decision, "evidence": {"findings": ids},
            "passes": {i: pass_ for i in ids}, "to": "qa_write"}


def test_us7_wrong_dismissals_empty_history():
    assert graph.wrong_dismissals([]) == {}


def test_us7_wrong_dismissals_counts_per_pass():
    entries = [_dismiss("wrong", ["T1"]), _dismiss("wrong", ["T2"])]
    assert graph.wrong_dismissals(entries) == {"tests": 2}


def test_us7_wrong_dismissals_counts_each_id_in_an_entry():
    assert graph.wrong_dismissals([_dismiss("wrong", ["T1", "T2", "T3"])]) == {"tests": 3}


def test_us7_wrong_dismissals_separate_passes_counted_separately():
    entries = [_dismiss("wrong", ["T1"]), _dismiss("wrong", ["C1"], "commit_decide", "commit"),
               _dismiss("wrong", ["T2"])]
    assert graph.wrong_dismissals(entries) == {"tests": 2, "commit": 1}


def test_us7_wrong_dismissals_ignores_overstated_and_correct():
    entries = [_dismiss("overstated", ["T1"]), _dismiss("correct", ["T2"])]
    assert graph.wrong_dismissals(entries) == {}


def test_us7_wrong_dismissals_mixed_decisions_count_only_wrong():
    entries = [_dismiss("overstated", ["T1"]), _dismiss("wrong", ["T2"]),
               _dismiss("correct", ["T3"]), _review()]
    assert graph.wrong_dismissals(entries) == {"tests": 1}


def test_us7_wrong_dismissals_uses_the_passes_map_per_id():
    e = {"node": "impl_decide", "decision": "wrong", "evidence": {"findings": ["A1", "B1"]},
         "passes": {"A1": "impl", "B1": "principles"}, "to": "x"}
    assert graph.wrong_dismissals([e]) == {"impl": 1, "principles": 1}


def test_us7_undismissed_without_dismissals_returns_all_fails():
    assert graph.undismissed([_review()], "tests_decide", ["T1", "T2"]) == ["T1", "T2"]


def test_us7_undismissed_after_dismissing_one():
    entries = [_review(), _dismiss("wrong", ["T1"])]
    assert graph.undismissed(entries, "tests_decide", ["T1", "T2"]) == ["T2"]


def test_us7_undismissed_overstated_also_dismisses():
    entries = [_review(), _dismiss("overstated", ["T1"])]
    assert graph.undismissed(entries, "tests_decide", ["T1", "T2"]) == ["T2"]


def test_us7_undismissed_all_dismissed_is_empty():
    entries = [_review(), _dismiss("wrong", ["T1"]), _dismiss("overstated", ["T2"])]
    assert graph.undismissed(entries, "tests_decide", ["T1", "T2"]) == []


def test_us7_undismissed_correct_does_not_dismiss():
    entries = [_review(), _dismiss("correct", ["T1"])]
    assert graph.undismissed(entries, "tests_decide", ["T1", "T2"]) == ["T1", "T2"]


def test_us7_undismissed_other_node_does_not_count():
    entries = [_review(), _dismiss("wrong", ["T1"], node="impl_decide")]
    assert graph.undismissed(entries, "tests_decide", ["T1", "T2"]) == ["T1", "T2"]


def test_us7_undismissed_newer_review_clears_earlier_dismissals():
    entries = [_review(), _dismiss("wrong", ["T1"]), _review()]
    assert graph.undismissed(entries, "tests_decide", ["T1", "T2"]) == ["T1", "T2"]


def test_us7_undismissed_counts_only_dismissals_after_last_review():
    entries = [_dismiss("wrong", ["T2"]), _review(), _dismiss("wrong", ["T1"])]
    assert graph.undismissed(entries, "tests_decide", ["T1", "T2"]) == ["T2"]


def test_us7_undismissed_follows_order_of_fails():
    entries = [_review(), _dismiss("wrong", ["T2"])]
    assert graph.undismissed(entries, "tests_decide", ["T3", "T2", "T1"]) == ["T3", "T1"]


def test_us7_undismissed_ignores_dismissed_ids_not_in_fails():
    entries = [_review(), _dismiss("wrong", ["T9"])]
    assert graph.undismissed(entries, "tests_decide", ["T1"]) == ["T1"]


def test_us7_undismissed_dismissals_accumulate_across_entries():
    entries = [_review(), _dismiss("wrong", ["T1"]), _dismiss("overstated", ["T3"])]
    assert graph.undismissed(entries, "tests_decide", ["T1", "T2", "T3"]) == ["T2"]


def test_us7_undismissed_does_not_mutate_inputs():
    entries = [_review(), _dismiss("wrong", ["T1"])]
    fails = ["T1", "T2"]
    graph.undismissed(entries, "tests_decide", fails)
    assert fails == ["T1", "T2"] and len(entries) == 2
