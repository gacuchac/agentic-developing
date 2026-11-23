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
