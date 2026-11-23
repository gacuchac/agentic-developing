"""Tests of scripts/workflow/contracts.py (US-7): the contract guard."""
from __future__ import annotations

import contracts


def _diff(path: str, body: str) -> str:
    return (
        f"diff --git a/{path} b/{path}\n"
        "index 1111111..2222222 100644\n"
        f"--- a/{path}\n"
        f"+++ b/{path}\n"
        "@@ -1,5 +1,5 @@\n"
        f"{body}"
    )


def test_us7_changed_signature_is_detected():
    d = _diff("scripts/x.py", "-def f(a):\n+def f(a, b):\n     return a\n")
    assert contracts.changed_signatures(d) == {"f"}


def test_us7_new_def_only_gives_empty_set():
    d = _diff("scripts/x.py", "+def f(a):\n+    return a\n")
    assert contracts.changed_signatures(d) == set()


def test_us7_private_helper_is_ignored():
    d = _diff("scripts/x.py", "-def _helper(a):\n+def _helper(a, b):\n")
    assert contracts.changed_signatures(d) == set()


def test_us7_tests_file_is_ignored():
    d = _diff("tests/test_x.py", "-def test_a(x):\n+def test_a(x, y):\n")
    assert contracts.changed_signatures(d) == set()


def test_us7_removed_public_def_counts():
    d = _diff("scripts/x.py", "-def gone(a):\n-    return a\n")
    assert contracts.changed_signatures(d) == {"gone"}


def test_us7_changed_in_one_file_while_other_only_adds():
    d = _diff("scripts/a.py", "-def f(a):\n+def f(a, b):\n") + _diff(
        "scripts/b.py", "+def g(a):\n+    return a\n"
    )
    assert contracts.changed_signatures(d) == {"f"}


def test_us7_nested_tests_dir_skipped_but_similar_name_is_not():
    d = _diff("pkg/tests/x.py", "-def hidden(a):\n+def hidden(a, b):\n") + _diff(
        "scripts/contest.py", "-def shown(a):\n+def shown(a, b):\n"
    )
    assert contracts.changed_signatures(d) == {"shown"}


def test_us7_indented_method_counts():
    d = _diff("scripts/x.py", "-    def g(self, a):\n+    def g(self, a, b):\n")
    assert contracts.changed_signatures(d) == {"g"}


def test_us7_header_lines_are_not_mistaken_for_defs():
    d = _diff("scripts/x.py", " unchanged\n")
    assert contracts.changed_signatures(d) == set()


def test_us7_empty_diff_gives_empty_set():
    assert contracts.changed_signatures("") == set()


def test_us7_uncovered_approved_text_naming_name_gives_empty():
    arch = "# Arch\nStatus: approved\n\n`f(a, b)` does things.\n"
    assert contracts.uncovered({"f"}, arch) == set()


def test_us7_uncovered_unapproved_text_returns_all_names():
    arch = "# Arch\nStatus: draft\n\n`f(a, b)` does things.\n"
    assert contracts.uncovered({"f"}, arch) == {"f"}


def test_us7_uncovered_approved_returns_only_unnamed():
    arch = "Status: approved\nf is covered here.\n"
    assert contracts.uncovered({"f", "h"}, arch) == {"h"}


def test_us7_uncovered_approval_is_case_insensitive():
    arch = "STATUS: APPROVED\nf is covered.\n"
    assert contracts.uncovered({"f"}, arch) == set()


def test_us7_uncovered_needs_status_and_approved_on_same_line():
    arch = "Status: draft\nThe plan is approved by nobody yet\nf is covered.\n"
    assert contracts.uncovered({"f"}, arch) == {"f"}


def test_us7_uncovered_empty_names_gives_empty():
    assert contracts.uncovered(set(), "no approval here") == set()
