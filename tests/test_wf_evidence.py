"""Tests for evidence.py: quote_near and quote_in (US-9)."""

import evidence


def make_text(n=20, **special):
    """n lines 'line k', with special {lineno: content} overrides."""
    lines = [f"line {k}" for k in range(1, n + 1)]
    for k, v in special.items():
        lines[int(k.lstrip("l")) - 1] = v
    return "\n".join(lines)


TEXT = make_text(l10="the quick brown fox")


# quote_near: window edges
def test_us9_near_found_on_exact_line():
    assert evidence.quote_near(TEXT, 10, "quick brown") is True


def test_us9_near_found_at_line_plus_2():
    assert evidence.quote_near(TEXT, 8, "quick brown") is True


def test_us9_near_found_at_line_minus_2():
    assert evidence.quote_near(TEXT, 12, "quick brown") is True


def test_us9_near_not_found_at_line_minus_3():
    assert evidence.quote_near(TEXT, 13, "quick brown") is False


def test_us9_near_not_found_at_line_plus_3():
    assert evidence.quote_near(TEXT, 7, "quick brown") is False


def test_us9_near_slack_zero_only_exact_line():
    assert evidence.quote_near(TEXT, 10, "quick", slack=0) is True
    assert evidence.quote_near(TEXT, 11, "quick", slack=0) is False
    assert evidence.quote_near(TEXT, 9, "quick", slack=0) is False


def test_us9_near_custom_slack():
    assert evidence.quote_near(TEXT, 14, "quick", slack=4) is True
    assert evidence.quote_near(TEXT, 15, "quick", slack=4) is False


def test_us9_near_other_line_content_not_matched():
    assert evidence.quote_near(TEXT, 10, "line 30") is False


# clipping at the ends
def test_us9_near_line_at_start_clipped_no_error():
    t = make_text(l1="alpha beta")
    assert evidence.quote_near(t, 1, "alpha") is True
    assert evidence.quote_near(t, 1, "line 3") is True
    assert evidence.quote_near(t, 1, "line 4") is False


def test_us9_near_line_at_end_clipped_no_error():
    t = make_text(n=20, l20="omega end")
    assert evidence.quote_near(t, 20, "omega") is True
    assert evidence.quote_near(t, 20, "line 18") is True
    assert evidence.quote_near(t, 20, "line 17") is False


def test_us9_near_line_beyond_end_no_error():
    assert evidence.quote_near(make_text(n=5), 100, "line 3") is False


def test_us9_near_line_zero_or_negative_no_error():
    t = make_text(l1="alpha")
    assert evidence.quote_near(t, 0, "alpha") is True
    assert evidence.quote_near(t, -5, "alpha") is False


# multi-line quotes
def test_us9_near_quote_spanning_two_lines_found():
    t = make_text(l10="first part", l11="second part")
    assert evidence.quote_near(t, 10, "first part second part") is True


def test_us9_near_spanning_quote_with_newline_in_quote_found():
    t = make_text(l10="first part", l11="second part")
    assert evidence.quote_near(t, 10, "first part\nsecond part") is True


def test_us9_near_spanning_quote_found_when_both_lines_in_window():
    t = make_text(l10="first part", l11="second part")
    assert evidence.quote_near(t, 12, "first part second part") is True


def test_us9_near_spanning_quote_not_found_when_one_line_outside():
    t = make_text(l10="first part", l11="second part")
    # window 13..17 contains neither; window 9..13 contains both; line 8 -> 6..10
    assert evidence.quote_near(t, 8, "first part second part") is False
    assert evidence.quote_near(t, 14, "first part second part") is False


def test_us9_near_spanning_quote_outside_by_one_edge_line():
    t = make_text(l10="first part", l11="second part")
    # line=13 -> window 11..15: line 10 outside
    assert evidence.quote_near(t, 13, "first part second part") is False


# whitespace normalisation
def test_us9_near_tabs_and_multiple_spaces_normalised():
    t = make_text(l10="the   quick\t\tbrown  fox")
    assert evidence.quote_near(t, 10, "the quick brown fox") is True


def test_us9_near_quote_whitespace_normalised():
    assert evidence.quote_near(TEXT, 10, "the \t quick   brown\nfox") is True


def test_us9_near_leading_trailing_whitespace_in_quote_ignored():
    assert evidence.quote_near(TEXT, 10, "  \tquick brown\n ") is True


def test_us9_near_empty_quote_false():
    assert evidence.quote_near(TEXT, 10, "") is False


def test_us9_near_whitespace_only_quote_false():
    assert evidence.quote_near(TEXT, 10, " \t\n  ") is False


def test_us9_near_empty_text_false():
    assert evidence.quote_near("", 1, "x") is False


# quote_in
def test_us9_in_found_in_one_of_many_texts():
    assert evidence.quote_in(["nothing here", "has the needle inside", "x"], "needle") is True


def test_us9_in_found_in_first_text():
    assert evidence.quote_in(["needle", "other"], "needle") is True


def test_us9_in_absent_from_all_texts_false():
    assert evidence.quote_in(["alpha", "beta"], "needle") is False


def test_us9_in_empty_texts_list_false():
    assert evidence.quote_in([], "needle") is False


def test_us9_in_whitespace_differs_found():
    assert evidence.quote_in(["the quick\n   brown\tfox jumps"], "quick brown  fox") is True


def test_us9_in_text_whitespace_differs_from_quote_found():
    assert evidence.quote_in(["a  b\t\tc"], "a b c") is True


def test_us9_in_quote_spans_lines_in_text():
    assert evidence.quote_in(["first part\nsecond part"], "first part second part") is True


def test_us9_in_quote_not_joined_across_texts():
    assert evidence.quote_in(["first part", "second part"], "first part second part") is False


def test_us9_in_empty_quote_false():
    assert evidence.quote_in(["anything"], "") is False


def test_us9_in_whitespace_only_quote_false():
    assert evidence.quote_in(["anything with spaces"], "  \t\n ") is False


def test_us9_in_empty_quote_false_with_empty_texts():
    assert evidence.quote_in([], "") is False


def test_us9_in_case_sensitive():
    assert evidence.quote_in(["Needle"], "needle") is False


# check_evidence (US-9)
FILES = {"a.py": make_text(l10="the quick brown fox")}


def make_facts(fails=("T1", "T2"), capped=()):
    return {"fails": list(fails), "capped": set(capped), "read": FILES.get}


def wrong_item(id="T1", file="a.py", line=10, quote="quick brown"):
    return {"id": id, "file": file, "line": line, "quote": quote}


def check(option, findings, facts=None):
    return evidence.check_evidence(option, {"findings": findings}, facts or make_facts())


def test_us9_correct_good_returns_empty():
    assert check("correct", ["T1", "T2"]) == []


def test_us9_correct_unknown_id_fails():
    errs = check("correct", ["T1", "ZZ9"])
    assert errs and any("ZZ9" in e for e in errs)


def test_us9_correct_empty_list_fails():
    assert check("correct", [])


def test_us9_correct_missing_findings_key_returns_errors():
    assert evidence.check_evidence("correct", {}, make_facts())


def test_us9_correct_several_unknown_ids_one_error_each():
    errs = check("correct", ["X1", "X2", "T1"])
    assert len(errs) >= 2
    assert any("X1" in e for e in errs) and any("X2" in e for e in errs)


def test_us9_overstated_good_returns_empty():
    assert check("overstated", [{"id": "T1", "reason": "cosmetic only"}]) == []


def test_us9_overstated_unknown_id_fails():
    errs = check("overstated", [{"id": "ZZ9", "reason": "fine"}])
    assert errs and any("ZZ9" in e for e in errs)


def test_us9_overstated_empty_reason_fails():
    errs = check("overstated", [{"id": "T1", "reason": ""}])
    assert errs and any("T1" in e for e in errs)


def test_us9_overstated_whitespace_reason_fails():
    errs = check("overstated", [{"id": "T1", "reason": "  \t\n "}])
    assert errs and any("T1" in e for e in errs)


def test_us9_overstated_missing_findings_key_returns_errors():
    assert evidence.check_evidence("overstated", {}, make_facts())


def test_us9_overstated_several_bad_one_error_each():
    errs = check("overstated", [{"id": "X1", "reason": "r"}, {"id": "T1", "reason": " "},
                                {"id": "T2", "reason": "ok"}])
    assert len(errs) >= 2
    assert any("X1" in e for e in errs) and any("T1" in e for e in errs)


def test_us9_wrong_good_returns_empty():
    assert check("wrong", [wrong_item()]) == []


def test_us9_wrong_unknown_id_fails():
    errs = check("wrong", [wrong_item(id="ZZ9")])
    assert errs and any("ZZ9" in e for e in errs)


def test_us9_wrong_capped_id_fails_even_with_good_quote():
    errs = check("wrong", [wrong_item()], make_facts(capped={"T1"}))
    assert errs and any("T1" in e for e in errs)


def test_us9_wrong_missing_file_fails():
    errs = check("wrong", [wrong_item(file="nope.py")])
    assert errs and any("nope.py" in e for e in errs)


def test_us9_wrong_quote_2_lines_off_passes():
    assert check("wrong", [wrong_item(line=12)]) == []
    assert check("wrong", [wrong_item(line=8)]) == []


def test_us9_wrong_quote_3_lines_off_fails():
    assert check("wrong", [wrong_item(line=13)])
    errs = check("wrong", [wrong_item(line=7)])
    assert errs and any("a.py" in e or "T1" in e for e in errs)


def test_us9_wrong_quote_absent_fails():
    assert check("wrong", [wrong_item(quote="not in file")])


def test_us9_wrong_missing_findings_key_returns_errors():
    assert evidence.check_evidence("wrong", {}, make_facts())


def test_us9_wrong_several_bad_one_error_each():
    errs = check("wrong", [wrong_item(id="X1"), wrong_item(id="T2", file="nope.py"),
                           wrong_item(id="T1", line=19)])
    assert len(errs) >= 3
    for k in ("X1", "nope.py"):
        assert any(k in e for e in errs)
