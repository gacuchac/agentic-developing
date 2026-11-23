"""Tests for evidence.py: quote_near and quote_in (US-9)."""

import pytest

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


# check_evidence: tests_wrong, code_wrong, escalate, architecture_stop, user_continue (US-9)
PLAN = "The tool must refuse an empty name.\nIt logs every call."
ASK = "Also keep the output sorted by date."


def dfacts(tmp_path, **over):
    f = {"failures": ["tests/t.py::test_a", "tests/t.py::test_b"], "docs": [PLAN, ASK],
         "run": tmp_path, "resume": ["write_unit", "qa"]}
    f.update(over)
    return f


def chk(option, ev, tmp_path, **over):
    return evidence.check_evidence(option, ev, dfacts(tmp_path, **over))


def tw(test="tests/t.py::test_a", quote="refuse an empty name"):
    return {"test": test, "quote": quote}


def test_us9_tests_wrong_good_returns_empty(tmp_path):
    assert chk("tests_wrong", tw(), tmp_path) == []


def test_us9_tests_wrong_quote_in_second_doc_passes(tmp_path):
    assert chk("tests_wrong", tw(quote="sorted by date"), tmp_path) == []


def test_us9_tests_wrong_test_not_a_failure_fails(tmp_path):
    errs = chk("tests_wrong", tw(test="tests/t.py::test_zzz"), tmp_path)
    assert errs and any("test_zzz" in e for e in errs)


def test_us9_tests_wrong_quote_not_in_docs_fails(tmp_path):
    errs = chk("tests_wrong", tw(quote="never written anywhere"), tmp_path)
    assert errs and any("never written anywhere" in e for e in errs)


def test_us9_tests_wrong_empty_quote_fails(tmp_path):
    assert chk("tests_wrong", tw(quote=""), tmp_path)


def test_us9_tests_wrong_missing_keys_return_errors(tmp_path):
    assert chk("tests_wrong", {}, tmp_path)
    assert chk("tests_wrong", {"test": "tests/t.py::test_a"}, tmp_path)
    assert chk("tests_wrong", {"quote": "refuse"}, tmp_path)


def test_us9_code_wrong_good_returns_empty(tmp_path):
    ev = {"tests": ["tests/t.py::test_a", "tests/t.py::test_b"]}
    assert chk("code_wrong", ev, tmp_path) == []


def test_us9_code_wrong_empty_list_fails(tmp_path):
    assert chk("code_wrong", {"tests": []}, tmp_path)


def test_us9_code_wrong_unknown_id_fails_naming_it(tmp_path):
    errs = chk("code_wrong", {"tests": ["tests/t.py::test_a", "tests/t.py::nope"]}, tmp_path)
    assert errs and any("nope" in e for e in errs)


def test_us9_code_wrong_missing_tests_key_returns_errors(tmp_path):
    assert chk("code_wrong", {}, tmp_path)


def test_us9_escalate_good_returns_empty(tmp_path):
    assert chk("escalate", {"question": "Which format should dates use?"}, tmp_path) == []


def test_us9_escalate_empty_question_fails(tmp_path):
    assert chk("escalate", {"question": ""}, tmp_path)


def test_us9_escalate_whitespace_question_fails(tmp_path):
    assert chk("escalate", {"question": " \t\n "}, tmp_path)


def test_us9_escalate_missing_question_returns_errors(tmp_path):
    assert chk("escalate", {}, tmp_path)


def test_us9_architecture_stop_relative_path_good(tmp_path):
    (tmp_path / "architecture-change-impl.md").write_text("x")
    assert chk("architecture_stop", {"path": "architecture-change-impl.md"}, tmp_path) == []


def test_us9_architecture_stop_relative_subdir_path_good(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "architecture-change-a.md").write_text("x")
    assert chk("architecture_stop", {"path": "sub/architecture-change-a.md"}, tmp_path) == []


def test_us9_architecture_stop_absolute_path_good(tmp_path):
    other = tmp_path / "elsewhere"
    other.mkdir()
    p = other / "architecture-change-qa.md"
    p.write_text("x")
    run = tmp_path / "run"
    run.mkdir()
    assert chk("architecture_stop", {"path": str(p)}, tmp_path, run=run) == []


def test_us9_architecture_stop_missing_file_fails(tmp_path):
    errs = chk("architecture_stop", {"path": "architecture-change-gone.md"}, tmp_path)
    assert errs and any("architecture-change-gone.md" in e for e in errs)


def test_us9_architecture_stop_wrong_name_fails(tmp_path):
    (tmp_path / "notes.md").write_text("x")
    errs = chk("architecture_stop", {"path": "notes.md"}, tmp_path)
    assert errs and any("notes.md" in e for e in errs)


def test_us9_architecture_stop_wrong_extension_fails(tmp_path):
    (tmp_path / "architecture-change-a.txt").write_text("x")
    assert chk("architecture_stop", {"path": "architecture-change-a.txt"}, tmp_path)


def test_us9_architecture_stop_missing_path_returns_errors(tmp_path):
    assert chk("architecture_stop", {}, tmp_path)


def test_us9_user_continue_good_returns_empty(tmp_path):
    assert chk("user_continue", {"user_said": "go ahead", "to": "qa"}, tmp_path) == []


def test_us9_user_continue_empty_user_said_fails(tmp_path):
    assert chk("user_continue", {"user_said": "", "to": "qa"}, tmp_path)
    assert chk("user_continue", {"user_said": "  ", "to": "qa"}, tmp_path)


def test_us9_user_continue_to_not_in_resume_fails_naming_it(tmp_path):
    errs = chk("user_continue", {"user_said": "go", "to": "merge_all"}, tmp_path)
    assert errs and any("merge_all" in e for e in errs)


def test_us9_user_continue_missing_keys_return_errors(tmp_path):
    assert chk("user_continue", {}, tmp_path)
    assert chk("user_continue", {"user_said": "go"}, tmp_path)


def test_us9_new_options_unknown_option_fails(tmp_path):
    errs = chk("bogus_option", {"question": "q"}, tmp_path)
    assert errs and any("bogus_option" in e for e in errs)


def test_us9_new_options_missing_facts_return_errors_not_exceptions(tmp_path):
    cases = {"tests_wrong": tw(), "code_wrong": {"tests": ["tests/t.py::test_a"]},
             "architecture_stop": {"path": "architecture-change-a.md"},
             "user_continue": {"user_said": "go", "to": "qa"}}
    for opt, ev in cases.items():
        assert evidence.check_evidence(opt, ev, {}), opt


# non-string and wrongly typed evidence values (US-9, fix unit 14-fix1)
import re

BAD_TEXT = [5, ["x"], None]


def lenient(tmp_path, v):
    """Facts that would accept str(v) / "" everywhere, so only the type check can reject."""
    s = [str(v), ""]
    text = make_text(l10="quick brown " + str(v))
    return dfacts(tmp_path, failures=["tests/t.py::test_a"] + s, docs=[PLAN, ASK] + s,
                  resume=["qa"] + s, read=lambda f: text, fails=["T1"], capped=set())


def run_bad(option, ev, field, tmp_path, v):
    facts = lenient(tmp_path, v)
    facts["fails"] = ["T1"]
    errs = evidence.check_evidence(option, ev, facts)
    assert errs, f"{option}.{field}={v!r} accepted"
    assert any(re.search(rf"\b{field}\b", e) for e in errs), (field, errs)


@pytest.mark.parametrize("v", BAD_TEXT)
def test_us9_escalate_non_str_question_fails(tmp_path, v):
    run_bad("escalate", {"question": v}, "question", tmp_path, v)


@pytest.mark.parametrize("field", ["user_said", "to"])
@pytest.mark.parametrize("v", BAD_TEXT)
def test_us9_user_continue_non_str_field_fails(tmp_path, field, v):
    run_bad("user_continue", {"user_said": "go", "to": "qa", field: v}, field, tmp_path, v)


@pytest.mark.parametrize("field", ["test", "quote"])
@pytest.mark.parametrize("v", BAD_TEXT)
def test_us9_tests_wrong_non_str_field_fails(tmp_path, field, v):
    run_bad("tests_wrong", {**tw(), field: v}, field, tmp_path, v)


@pytest.mark.parametrize("v", BAD_TEXT)
def test_us9_architecture_stop_non_str_path_fails(tmp_path, v):
    (tmp_path / "architecture-change-a.md").write_text("x")
    run_bad("architecture_stop", {"path": v}, "path", tmp_path, v)


@pytest.mark.parametrize("v", BAD_TEXT)
def test_us9_overstated_non_str_reason_fails(tmp_path, v):
    ev = {"findings": [{"id": "T1", "reason": v}]}
    run_bad("overstated", ev, "reason", tmp_path, v)


@pytest.mark.parametrize("field", ["file", "quote"])
@pytest.mark.parametrize("v", BAD_TEXT)
def test_us9_wrong_non_str_field_fails(tmp_path, field, v):
    ev = {"findings": [{**wrong_item(id="T1"), field: v}]}
    run_bad("wrong", ev, field, tmp_path, v)


@pytest.mark.parametrize("v", ["10", 10.0, None, [10]])
def test_us9_wrong_non_int_line_fails(tmp_path, v):
    ev = {"findings": [wrong_item(id="T1", line=v)]}
    errs = evidence.check_evidence("wrong", ev, lenient(tmp_path, "x"))
    assert errs


def test_us9_code_wrong_str_tests_names_tests(tmp_path):
    errs = chk("code_wrong", {"tests": "t1"}, tmp_path, failures=["t1"])
    assert errs and any(re.search(r"\btests\b", e) for e in errs)


@pytest.mark.parametrize("option", ["correct", "overstated", "wrong"])
def test_us9_findings_str_fails_without_raising(option, tmp_path):
    errs = evidence.check_evidence(option, {"findings": "T1"}, lenient(tmp_path, "x"))
    assert errs and any("findings" in e for e in errs)


def test_us9_valid_baselines_still_pass(tmp_path):
    (tmp_path / "architecture-change-a.md").write_text("x")
    assert chk("escalate", {"question": "q?"}, tmp_path) == []
    assert chk("user_continue", {"user_said": "go", "to": "qa"}, tmp_path) == []
    assert chk("tests_wrong", tw(), tmp_path) == []
    assert chk("architecture_stop", {"path": "architecture-change-a.md"}, tmp_path) == []


def test_us9_architecture_stop_path_object_to_real_file_fails(tmp_path):
    f = tmp_path / "architecture-change-x.md"
    f.write_text("x")
    errs = chk("architecture_stop", {"path": f}, tmp_path)
    assert errs and any(re.search(r"\bpath\b", e) for e in errs)


def test_us9_wrong_path_object_file_with_valid_lookup_fails():
    import pathlib
    ev = {"findings": [wrong_item(id="T1", file=pathlib.Path("a.py"))]}
    errs = evidence.check_evidence("wrong", ev, make_facts())
    assert errs and any(re.search(r"\bfile\b", e) for e in errs)
