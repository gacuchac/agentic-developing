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


def test_us7_unit_loop_nodes_reachable_from_write_unit():
    seen, todo = set(), ["write_unit"]
    while todo:
        n = todo.pop()
        if n in seen:
            continue
        seen.add(n)
        todo.extend(EDGES[n].values())
    unit_loop = {
        "write_unit", "qa_write", "red_run", "red_decide", "commit_tests", "implement", "tests_review",
        "tests_decide", "qa_fix", "verify", "fail_decide", "impl_review", "impl_decide", "commit_fix", "next_unit",
        "user", "done",
    }  # fmt: skip
    assert unit_loop <= seen


def test_us7_removed_nodes_are_gone():
    for node in ("count_lines", "run_tests", "commit", "commit_reviews", "commit_decide"):
        assert node not in EDGES, node


def test_us7_stops_go_to_user():
    assert graph.STOPS == {"escalate": "user", "architecture_stop": "user"}


def test_us7_red_run_expected_commits_tests_unexpected_decides():
    assert EDGES["red_run"] == {"expected": "commit_tests", "unexpected": "red_decide"}


def test_us7_red_decide_tests_wrong_rewrites():
    assert EDGES["red_decide"]["tests_wrong"] == "qa_write"


def test_us7_commit_tests_done_goes_to_implement_refused_back_to_qa_write():
    assert EDGES["commit_tests"] == {"done": "implement", "refused": "qa_write"}


def test_us7_implement_goes_to_tests_review():
    assert EDGES["implement"] == {"recorded": "tests_review"}


def test_us7_tests_review_edges():
    assert EDGES["tests_review"] == {"PASS": "verify", "CHANGES": "tests_decide", "MALFORMED": "user"}


def test_us7_tests_decide_correct_goes_to_qa_fix_dismissed_go_to_verify():
    assert EDGES["tests_decide"]["correct"] == "qa_fix"
    assert EDGES["tests_decide"]["overstated"] == "verify"
    assert EDGES["tests_decide"]["wrong"] == "verify"


def test_us7_qa_fix_recorded_goes_to_commit_tests():
    assert EDGES["qa_fix"] == {"recorded": "commit_tests"}


def test_us7_verify_outcomes():
    assert EDGES["verify"] == {
        "fast": "commit_fix",
        "full": "impl_review",
        "tests_touched": "implement",
        "fail": "fail_decide",
    }


def test_us7_fail_decide_code_wrong_implements_tests_wrong_goes_to_qa_fix():
    assert EDGES["fail_decide"]["code_wrong"] == "implement"
    assert EDGES["fail_decide"]["tests_wrong"] == "qa_fix"


def test_us7_impl_review_edges():
    assert EDGES["impl_review"] == {"PASS": "commit_fix", "CHANGES": "impl_decide", "MALFORMED": "user"}


def test_us7_impl_decide_correct_implements_dismissed_commit():
    assert EDGES["impl_decide"]["correct"] == "implement"
    assert EDGES["impl_decide"]["overstated"] == "commit_fix"
    assert EDGES["impl_decide"]["wrong"] == "commit_fix"


def test_us7_commit_fix_done_goes_to_next_unit_refused_to_implement():
    assert EDGES["commit_fix"] == {"done": "next_unit", "refused": "implement"}


def test_us7_next_unit_more_loops_last_goes_to_subtract_finished_to_full_suite():
    assert EDGES["next_unit"] == {"more": "write_unit", "last": "subtract", "finished": "full_suite"}


def test_us7_subtract_recorded_goes_to_subtract_check():
    assert EDGES["subtract"] == {"recorded": "subtract_check"}


def test_us7_subtract_check_edges():
    assert EDGES["subtract_check"] == {"pass": "commit_subtract", "nothing": "branch_reviews", "fail": "subtract"}


def test_us7_commit_subtract_done_goes_to_branch_reviews_refused_back_to_subtract():
    assert EDGES["commit_subtract"] == {"done": "branch_reviews", "refused": "subtract"}


def test_us7_branch_reviews_edges():
    assert EDGES["branch_reviews"] == {"PASS": "full_suite", "CHANGES": "branch_decide", "MALFORMED": "user"}


def test_us7_branch_decide_correct_writes_unit_dismissed_go_to_full_suite():
    assert EDGES["branch_decide"]["correct"] == "write_unit"
    assert EDGES["branch_decide"]["overstated"] == "full_suite"
    assert EDGES["branch_decide"]["wrong"] == "full_suite"


def test_us7_subtract_runs_the_implementer_subtract_step():
    assert graph.AGENT_STEPS["subtract"] == ("implementer", "subtract")
    assert graph.kind("subtract") == "agent"


def test_us7_branch_reviews_runs_principles_and_alternatives_once():
    assert graph.REVIEW_PASSES["branch_reviews"] == ("principles", "alternatives")


def test_us7_branch_decide_and_aa_decide_decide_on_their_reviews():
    assert graph.DECIDES_ON["branch_decide"] == "branch_reviews"
    assert graph.DECIDES_ON["aa_decide"] == "answers_ask"


def test_us7_subtract_check_fail_and_commit_subtract_refused_are_back_edges():
    assert graph.BACK_EDGES[("subtract_check", "fail")] == "subtract"
    assert graph.BACK_EDGES[("commit_subtract", "refused")] == "subtract"


def test_us7_later_review_decisions_dismissed_skip_ahead():
    assert EDGES["aa_decide"]["wrong"] == "done"


def test_us7_user_and_done_have_no_edges():
    assert EDGES["user"] == {}
    assert EDGES["done"] == {}


def test_us7_edges_match_the_unit_loop_table():
    expected = {
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
        "next_unit": {"more": "write_unit", "last": "subtract", "finished": "full_suite"},
        "subtract": {"recorded": "subtract_check"},
        "subtract_check": {"pass": "commit_subtract", "nothing": "branch_reviews", "fail": "subtract"},
        "commit_subtract": {"done": "branch_reviews", "refused": "subtract"},
        "branch_reviews": {"PASS": "full_suite", "CHANGES": "branch_decide", "MALFORMED": "user"},
        "branch_decide": {"correct": "write_unit", "overstated": "full_suite", "wrong": "full_suite"},
        "full_suite": {"pass": "answers_ask", "fail": "full_decide"},
        "full_decide": {"code_wrong": "write_unit"},
        "answers_ask": {"PASS": "done", "CHANGES": "aa_decide", "MALFORMED": "user"},
        "aa_decide": {"correct": "write_unit", "overstated": "done", "wrong": "done"},
        "user": {},
        "done": {},
    }
    for node in expected:
        if node.endswith("_decide"):
            expected[node] = {**expected[node], **graph.STOPS}
    assert expected == graph.EDGES


def test_us7_agent_steps_exact():
    assert graph.AGENT_STEPS == {
        "qa_write": ("qa", "write"),
        "qa_fix": ("qa", "fix"),
        "implement": ("implementer", "code"),
        "subtract": ("implementer", "subtract"),
    }


def test_us7_review_passes_exact():
    assert graph.REVIEW_PASSES == {
        "tests_review": ("tests",),
        "impl_review": ("impl",),
        "branch_reviews": ("principles", "alternatives"),
        "answers_ask": ("answers-ask",),
    }


def test_us7_decides_on_exact():
    assert graph.DECIDES_ON == {
        "tests_decide": "tests_review",
        "impl_decide": "impl_review",
        "branch_decide": "branch_reviews",
        "aa_decide": "answers_ask",
    }


def test_us7_back_edges_exact_with_targets():
    assert graph.BACK_EDGES == {
        ("tests_decide", "correct"): "qa_fix",
        ("red_decide", "tests_wrong"): "qa_write",
        ("impl_decide", "correct"): "implement",
        ("fail_decide", "code_wrong"): "implement",
        ("fail_decide", "tests_wrong"): "qa_fix",
        ("verify", "tests_touched"): "implement",
        ("commit_tests", "refused"): "qa_write",
        ("commit_fix", "refused"): "implement",
        ("subtract_check", "fail"): "subtract",
        ("commit_subtract", "refused"): "subtract",
    }


def test_us7_caps():
    assert graph.ROUND_CAP == 3
    assert graph.WRONG_CAP == 2


def test_us7_kind_of_every_node():
    agent = {"qa_write", "qa_fix", "implement", "subtract"}
    decide = {"red_decide", "tests_decide", "impl_decide", "fail_decide", "full_decide", "aa_decide", "branch_decide"}
    auto = {
        "write_unit", "red_run", "commit_tests", "tests_review", "verify", "impl_review", "commit_fix",
        "next_unit", "full_suite", "answers_ask",
        "subtract_check", "commit_subtract", "branch_reviews",
    }  # fmt: skip
    expected = {n: "agent" for n in agent}
    expected.update({n: "decide" for n in decide})
    expected.update({n: "auto" for n in auto})
    expected.update({"user": "user", "done": "end"})
    assert {n: graph.kind(n) for n in EDGES} == expected


def test_us7_commit_fix_is_auto():
    assert graph.kind("commit_fix") == "auto"
    assert graph.kind("qa_fix") == "agent"


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
    for n in range(6):
        assert graph.back_rounds([_impl_back()] * n, "implement") == n


def test_us7_forward_entries_do_not_count():
    forward = {"node": "tests_review", "outcome": "PASS", "to": "implement"}
    entries = [forward, forward, forward, _impl_back()]
    assert graph.back_rounds(entries, "implement") == 1
    assert graph.cap_reached(entries, "impl_decide") is False


def test_us7_outcome_key_back_edges_count():
    touched = {"node": "verify", "outcome": "tests_touched", "to": "implement"}
    assert graph.back_rounds([touched, touched], "implement") == 2


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
    entries = [_impl_back(), _user_continue(), _impl_back(), _impl_back(), _user_continue(), _impl_back()]
    assert graph.back_rounds(entries, "implement") == 1


def test_us7_verify_tests_touched_three_times_caps_verify():
    over = {"node": "verify", "outcome": "tests_touched", "to": "implement"}
    assert graph.cap_reached([over, over], "verify") is False
    assert graph.cap_reached([over, over, over], "verify") is True


def test_us7_rounds_to_implement_pool_across_nodes():
    entries = [
        _impl_back(),
        _back("fail_decide", "code_wrong", "implement"),
        {"node": "verify", "outcome": "tests_touched", "to": "implement"},
    ]
    assert graph.back_rounds(entries, "implement") == 3
    assert graph.cap_reached(entries, "impl_decide") is True


def test_us7_back_edge_to_other_target_does_not_count():
    to_qa = [_back("tests_decide", "correct", "qa_fix")] * 3
    assert graph.back_rounds(to_qa, "implement") == 0
    assert graph.back_rounds(to_qa, "qa_fix") == 3
    assert graph.cap_reached(to_qa, "impl_decide") is False
    assert graph.cap_reached(to_qa, "tests_decide") is True


def test_us7_cap_reached_false_for_node_without_back_edges():
    entries = [_impl_back()] * 5
    assert graph.cap_reached(entries, "qa_write") is False


def test_us7_cap_reached_any_back_edge_of_node_triggers():
    entries = [_back("tests_decide", "correct", "qa_fix")] * 3
    assert graph.cap_reached(entries, "fail_decide") is True
    assert graph.cap_reached(entries, "red_decide") is False


def _review(node="tests_review", outcome="CHANGES"):
    return {
        "node": node,
        "outcome": outcome,
        "verdict": outcome,
        "reviews": [{"pass": "tests", "review": "review-tests-1.md", "verdict": outcome, "fails": ["T1", "T2"]}],
    }


def _dismiss(decision, ids, node="tests_decide", pass_="tests"):
    return {
        "node": node,
        "decision": decision,
        "evidence": {"findings": ids},
        "passes": {i: pass_ for i in ids},
        "to": "qa_write",
    }


def test_us7_wrong_dismissals_empty_history():
    assert graph.wrong_dismissals([]) == {}


def test_us7_wrong_dismissals_counts_per_pass():
    entries = [_dismiss("wrong", ["T1"]), _dismiss("wrong", ["T2"])]
    assert graph.wrong_dismissals(entries) == {"tests": 2}


def test_us7_wrong_dismissals_counts_each_id_in_an_entry():
    assert graph.wrong_dismissals([_dismiss("wrong", ["T1", "T2", "T3"])]) == {"tests": 3}


def test_us7_wrong_dismissals_separate_passes_counted_separately():
    entries = [
        _dismiss("wrong", ["T1"]),
        _dismiss("wrong", ["C1"], "commit_decide", "commit"),
        _dismiss("wrong", ["T2"]),
    ]
    assert graph.wrong_dismissals(entries) == {"tests": 2, "commit": 1}


def test_us7_wrong_dismissals_ignores_overstated_and_correct():
    entries = [_dismiss("overstated", ["T1"]), _dismiss("correct", ["T2"])]
    assert graph.wrong_dismissals(entries) == {}


def test_us7_wrong_dismissals_mixed_decisions_count_only_wrong():
    entries = [_dismiss("overstated", ["T1"]), _dismiss("wrong", ["T2"]), _dismiss("correct", ["T3"]), _review()]
    assert graph.wrong_dismissals(entries) == {"tests": 1}


def test_us7_wrong_dismissals_uses_the_passes_map_per_id():
    e = {
        "node": "impl_decide",
        "decision": "wrong",
        "evidence": {"findings": ["A1", "B1"]},
        "passes": {"A1": "impl", "B1": "principles"},
        "to": "x",
    }
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


def _wrongs(pass_, n, node="tests_decide"):
    return [_dismiss("wrong", [f"{pass_}{i}"], node=node, pass_=pass_) for i in range(n)]


def _qa_back():
    return _back("tests_decide", "correct", "qa_fix")


STOP_LIST = ["escalate", "architecture_stop"]


def test_us7_options_tests_decide_no_history():
    assert graph.legal_options("tests_decide", [], set()) == [
        "correct",
        "overstated",
        "wrong",
        "escalate",
        "architecture_stop",
    ]


def test_us7_options_follow_edges_order_for_every_decide_node():
    for node in EDGES:
        if graph.kind(node) == "decide":
            assert graph.legal_options(node, [], set()) == list(EDGES[node])


def test_us7_options_uncovered_leaves_only_architecture_stop():
    assert graph.legal_options("tests_decide", [], {"f"}) == ["architecture_stop"]
    assert graph.legal_options("full_decide", [], {"a", "b"}) == ["architecture_stop"]


def test_us7_options_cap_reached_leaves_escalate_and_architecture_stop():
    entries = [_qa_back()] * 3
    assert graph.legal_options("tests_decide", entries, set()) == STOP_LIST


def test_us7_options_under_cap_keeps_all_edges():
    entries = [_qa_back()] * 2
    assert graph.legal_options("tests_decide", entries, set()) == list(EDGES["tests_decide"])


def test_us7_options_cap_on_fail_decide_and_impl_decide():
    assert graph.legal_options("fail_decide", [_back("fail_decide", "code_wrong", "implement")] * 3, set()) == STOP_LIST
    assert graph.legal_options("impl_decide", [_impl_back()] * 3, set()) == STOP_LIST


def test_us7_options_cap_after_user_continue_is_reset():
    entries = [_qa_back()] * 3 + [_user_continue("qa_fix")]
    assert graph.legal_options("tests_decide", entries, set()) == list(EDGES["tests_decide"])


def test_us7_options_two_wrong_dismissals_remove_wrong():
    assert graph.legal_options("tests_decide", _wrongs("tests", 2), set()) == [
        "correct",
        "overstated",
        "escalate",
        "architecture_stop",
    ]


def test_us7_options_one_wrong_dismissal_keeps_wrong():
    assert "wrong" in graph.legal_options("tests_decide", _wrongs("tests", 1), set())


def test_us7_options_wrong_dismissals_of_other_pass_do_not_count():
    assert "wrong" in graph.legal_options("tests_decide", _wrongs("impl", 2, "impl_decide"), set())


def test_us7_options_impl_decide_two_wrong_removes_wrong():
    assert graph.legal_options("impl_decide", _wrongs("impl", 2, "impl_decide"), set()) == [
        "correct",
        "overstated",
        "escalate",
        "architecture_stop",
    ]


def test_us7_options_decide_without_review_pass_never_loses_wrong_rule():
    assert graph.legal_options("full_decide", [], set()) == ["code_wrong", "escalate", "architecture_stop"]
    assert graph.legal_options("red_decide", [], set()) == list(EDGES["red_decide"])


def test_us7_options_uncovered_beats_cap():
    assert graph.legal_options("tests_decide", [_qa_back()] * 3, {"f"}) == ["architecture_stop"]


def test_us7_options_cap_beats_wrong_rule():
    entries = [_qa_back()] * 3 + _wrongs("tests", 2)
    assert graph.legal_options("tests_decide", entries, set()) == STOP_LIST


def test_us7_options_uncovered_beats_cap_and_wrong_rule():
    entries = [_qa_back()] * 3 + _wrongs("tests", 2)
    assert graph.legal_options("tests_decide", entries, {"f"}) == ["architecture_stop"]


def test_us7_options_user_gives_user_continue():
    assert graph.legal_options("user", [], set()) == ["user_continue"]
    assert graph.legal_options("user", [_qa_back()] * 3, {"f"}) == ["user_continue"]


def test_us7_options_done_has_none():
    assert graph.legal_options("done", [], set()) == []


def test_us7_options_agent_nodes_have_none():
    assert graph.legal_options("qa_write", [], set()) == []
    assert graph.legal_options("implement", [], {"f"}) == []


def test_us7_options_stalled_commit_fix_offers_escalate_and_architecture_stop():
    assert graph.legal_options("commit_fix", [], set()) == ["escalate", "architecture_stop"]


def test_us7_options_every_auto_node_gives_the_stops():
    for node in EDGES:
        if graph.kind(node) == "auto":
            assert graph.legal_options(node, [], set()) == STOP_LIST


def test_us7_options_returns_a_fresh_list_and_keeps_inputs():
    entries, unc = [_qa_back()] * 3, {"f"}
    first = graph.legal_options("commit_fix", entries, unc)
    first.append("x")
    assert graph.legal_options("commit_fix", entries, unc) == STOP_LIST
    assert entries == [_qa_back()] * 3 and unc == {"f"}


def test_us9_wrong_dismissals_counts_dict_findings_like_bare_ids():
    entry = {
        "decision": "wrong",
        "evidence": {"findings": [{"id": "T1", "reason": "r"}, {"id": "T2", "reason": "r"}]},
        "passes": {"T1": "tests", "T2": "tests"},
    }
    assert graph.wrong_dismissals([entry]) == {"tests": 2}


def test_us9_undismissed_accepts_dict_findings_like_bare_ids():
    entries = [
        {
            "node": "tests_decide",
            "decision": "overstated",
            "evidence": {"findings": [{"id": "T1", "reason": "r"}]},
            "passes": {"T1": "tests"},
        },
    ]
    assert graph.undismissed(entries, "tests_decide", ["T1", "T2"]) == ["T2"]
