"""Tests for decisions (US-11)."""

import decisions

HEADER = "ts\tphase\tdecision\twhy\tevidence\tresult"

WRONG = {
    "unit": "3",
    "node": "tests_decide",
    "decision": "wrong",
    "evidence": {"findings": [{"id": "T1", "file": "a.py", "line": 12, "quote": "x = 1"}]},
    "to": "verify",
    "t": "2026-11-23T10:00:00",
}

COMMIT = {
    "unit": "3",
    "node": "commit_fix",
    "outcome": "done",
    "sha": "abc1234",
    "message": "US-1: do it",
    "to": "next_unit",
    "t": "2026-11-23T10:05:00",
}


def test_us11_wrong_entry_gives_file_line_evidence_and_quote():
    cells = decisions.row(WRONG)
    assert len(cells) == 6
    assert cells[0] == "2026-11-23T10:00:00"
    assert cells[1] == "u3 tests_decide"
    assert cells[2] == "wrong"
    assert "x = 1" in cells[3]
    assert "a.py:12" in cells[4]
    assert cells[5] == "verify"


def test_us11_commit_entry_gives_sha_and_message():
    cells = decisions.row(COMMIT)
    assert len(cells) == 6
    assert cells[2] == "done"
    assert cells[3] == "US-1: do it"
    assert cells[4] == "abc1234"
    assert cells[5] == "next_unit"


def test_us11_append_text_cleans_tab_newline_and_leading_equals():
    out = decisions.append_text("", ["a", "b\tc\nd", "=SUM(1)", "d", "e", "f"])
    row = out.splitlines()[1].split("\t")
    assert row[1] == "b c d"
    assert row[2] == "'=SUM(1)"
    assert len(row) == 6


def test_us11_append_text_prefixes_plus_minus_at():
    out = decisions.append_text("", ["+a", "-b", "@c", "d", "e", "f"])
    row = out.splitlines()[1].split("\t")
    assert row[:3] == ["'+a", "'-b", "'@c"]


def test_us11_header_written_once_when_empty():
    first = decisions.append_text("", ["1", "2", "3", "4", "5", "6"])
    assert first.splitlines()[0] == HEADER
    assert first.endswith("\n")
    second = decisions.append_text(first, ["7", "8", "9", "10", "11", "12"])
    assert second.startswith(first)
    assert second.count(HEADER) == 1
    assert second.splitlines()[-1].split("\t") == ["7", "8", "9", "10", "11", "12"]


def test_us9_correct_entry_with_bare_id_findings_shows_the_id_as_evidence():
    entry = {
        "unit": "3",
        "node": "tests_decide",
        "decision": "correct",
        "evidence": {"findings": ["T1"]},
        "to": "qa_fix",
        "t": "2026-11-23T10:00:00",
    }
    cells = decisions.row(entry)
    assert "T1" in cells[4]
