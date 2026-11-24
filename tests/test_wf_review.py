"""Tests for review.py: the verdict comes from criterion lines, never the VERDICT line."""

from pathlib import Path

import review

ROOT = Path(__file__).resolve().parent.parent
PASSES = ROOT / ".claude" / "review-passes"

COMMIT_3 = """<!-- pass: commit | model: gpt-6-luna | base: commit 51611207378a5a7b882d1f5d8c3340feae13964c | exit: 0 | 2026-11-23 13:54:36 -->
VERDICT: CHANGES
C1: PASS — `.claude/review-passes/impl.md:1` names US-4 and states one goal: add light `impl` and `tests` rubrics judged against `unit.md`.
C2: PASS — `.claude/review-passes/tests.md:1` and `.claude/review-passes/impl.md:1` define the two requested uncommitted-change reviews, and `tests/test_codex_review_commit.py:125` checks that every pass has a prompt file.
C3: PASS — The diff adds only the two US-4 rubrics and their prompt-file test, as specified in subtask 3.
C4: PASS — The rubrics support US-4’s light review passes and match subtask 3’s planned files and behavior.
C5: PASS — `tests/test_codex_review_commit.py:125` adds a discovery check without hard-coded expected outputs, input special-casing, or weakening existing tests.
"""

ALT_8 = """<!-- pass: alternatives | model: gpt-6-luna | base: commit 7fc5de87ead776927c4673b3ec350ac72b1a688a | exit: 0 | 2026-11-23 15:22:21 -->
VERDICT: PASS

L1: N/A — [state.py](/Users/tamarmilstein/Developing/scripts/workflow/state.py:10) implements the scoped state helpers directly, and no clearly smaller approach preserves the requested API and atomic save behavior.

L2: FAIL — [state.py](/Users/tamarmilstein/Developing/scripts/workflow/state.py:28) leaves the temporary file behind if JSON serialization fails; use `try/finally` to unlink it on failure, trading a few lines for cleanup of an orphaned temp file.

L3: N/A — [state.py](/Users/tamarmilstein/Developing/scripts/workflow/state.py:28) uses standard-library JSON, temporary-file, and atomic-replace functions rather than rebuilding existing functionality.
"""

C_IDS = ["C1", "C2", "C3", "C4", "C5"]


def _lines(*lines):
    return "VERDICT: PASS\n" + "\n".join(lines) + "\n"


def test_us8_rubric_ids_of_commit_md():
    assert review.rubric_ids((PASSES / "commit.md").read_text()) == C_IDS


def test_us8_rubric_ids_of_principles_md():
    ids = review.rubric_ids((PASSES / "principles.md").read_text())
    assert ids == ["P1", "P3", "P5", "P6"]


def test_us8_rubric_ids_only_matches_dash_id_dot_lines_in_order():
    rubric = "intro C9. no\n- B2. second\n- A1. first\n  - D4. indented\n- E5: colon\n- F6.nospace\n"
    assert review.rubric_ids(rubric) == ["B2", "A1"]


def test_us8_rubric_ids_empty_rubric():
    assert review.rubric_ids("no criteria here\n") == []


def test_us8_real_review_all_pass_ignores_verdict_changes():
    assert review.derive_verdict(COMMIT_3, C_IDS) == ("PASS", [])


def test_us8_parse_criteria_real_commit_review():
    assert review.parse_criteria(COMMIT_3) == {i: "PASS" for i in C_IDS}


def test_us8_real_alternatives_review_fail_beats_verdict_pass():
    assert review.derive_verdict(ALT_8, ["L1", "L2", "L3"]) == ("CHANGES", ["L2"])


def test_us8_parse_criteria_blank_lines_between_criteria():
    assert review.parse_criteria(ALT_8) == {"L1": "N/A", "L2": "FAIL", "L3": "N/A"}


def test_us8_verdict_pass_with_c2_fail_gives_changes():
    text = _lines(*(f"{i}: {'FAIL' if i == 'C2' else 'PASS'} — x" for i in C_IDS))
    assert review.derive_verdict(text, C_IDS) == ("CHANGES", ["C2"])


def test_us8_verdict_changes_line_has_no_effect():
    text = "VERDICT: CHANGES\n" + "\n".join(f"{i}: PASS — ok" for i in C_IDS)
    assert review.derive_verdict(text, C_IDS) == ("PASS", [])


def test_us8_no_verdict_line_still_derives():
    text = "\n".join(f"{i}: PASS" for i in C_IDS)
    assert review.derive_verdict(text, C_IDS) == ("PASS", [])


def test_us8_missing_expected_id_is_malformed():
    text = _lines(*(f"{i}: PASS — ok" for i in C_IDS if i != "C4"))
    assert review.derive_verdict(text, C_IDS) == ("MALFORMED", [])


def test_us8_missing_id_is_malformed_even_with_a_fail_present():
    text = _lines("C1: FAIL — x", "C2: PASS", "C3: PASS", "C5: PASS")
    assert review.derive_verdict(text, C_IDS) == ("MALFORMED", [])


def test_us8_empty_expected_is_malformed():
    assert review.derive_verdict(COMMIT_3, []) == ("MALFORMED", [])


def test_us8_na_does_not_fail():
    text = _lines("C1: N/A — nothing", "C2: PASS", "C3: N/A")
    assert review.derive_verdict(text, ["C1", "C2", "C3"]) == ("PASS", [])


def test_us8_na_counts_as_present():
    assert review.parse_criteria("C1: N/A — x\n") == {"C1": "N/A"}


def test_us8_dash_prefix_format():
    assert review.parse_criteria("- C1: PASS\n- C2: FAIL — bad\n") == {"C1": "PASS", "C2": "FAIL"}


def test_us8_bold_id_format():
    assert review.parse_criteria("**P2**: FAIL\n**P3**: PASS — fine\n") == {"P2": "FAIL", "P3": "PASS"}


def test_us8_bold_verdict_word_format():
    assert review.parse_criteria("C1: **PASS** — ok\nC2: **FAIL**\n") == {"C1": "PASS", "C2": "FAIL"}


def test_us8_dash_bold_format_derives_changes():
    text = "- **C1**: PASS\n- **C2**: FAIL\n"
    assert review.derive_verdict(text, ["C1", "C2"]) == ("CHANGES", ["C2"])


def test_us8_leading_whitespace_allowed():
    assert review.parse_criteria("   C1: PASS\n\t- C2: FAIL\n") == {"C1": "PASS", "C2": "FAIL"}


def test_us8_fail_on_any_line_wins_over_pass():
    assert review.parse_criteria("C1: PASS\nC1: FAIL — later\n") == {"C1": "FAIL"}
    assert review.parse_criteria("C1: FAIL\nC1: PASS — later\n") == {"C1": "FAIL"}


def test_us8_fail_wins_in_derive_verdict():
    text = "C1: FAIL\nC1: PASS\nC2: PASS\n"
    assert review.derive_verdict(text, ["C1", "C2"]) == ("CHANGES", ["C1"])


def test_us8_fail_ids_listed_in_review_order_of_expected():
    text = "C1: FAIL\nC2: PASS\nC3: FAIL\n"
    assert review.derive_verdict(text, ["C1", "C2", "C3"]) == ("CHANGES", ["C1", "C3"])


def test_us8_word_boundary_after_verdict_word():
    assert review.parse_criteria("C1: PASSED\nC2: FAILURE\n") == {}


def test_us8_ignores_prose_mentions_and_lowercase_ids():
    text = "see C1: PASS in the notes\nc1: PASS\nVERDICT: PASS\n"
    assert review.parse_criteria(text) == {}


def test_us8_extra_ids_not_expected_are_ignored():
    text = "C1: PASS\nC9: FAIL\n"
    assert review.derive_verdict(text, ["C1"]) == ("PASS", [])


def test_us8_empty_review_with_expected_is_malformed():
    assert review.derive_verdict("", ["C1"]) == ("MALFORMED", [])


# review_args / saved_path. Assumption: Path values appear as str in the list.
import sys

sys.path.insert(0, str(ROOT / "scripts"))
import codex_review  # noqa: E402

RUN = Path("/runs/p/t")
SHA = "a" * 40
HEAD_ARGS = ["--ask-file", "/runs/p/t/ask.md", "--plan-file", "/runs/p/t/plan.md", "--run-dir", "/runs/p/t"]
UNIT = ["--context-file", "/runs/p/t/unit.md"]
ARCH = ["--context-file", "/runs/p/t/architecture.md"]


def _given(args):
    flags = {a: args[i + 1] for i, a in enumerate(args) if a.startswith("--")}
    return {k[2:].replace("-", "_"): v for k, v in flags.items()}


def test_us8_review_args_tests_has_unit_and_no_commit():
    got = review.review_args("tests", RUN, "plan.md", None, None)
    assert got[: 1 + len(HEAD_ARGS)] == ["tests", *HEAD_ARGS]
    assert "--commit" not in got
    assert "/runs/p/t/unit.md" in got


def test_us8_review_args_impl_has_unit_then_architecture():
    assert review.review_args("impl", RUN, "plan.md", None, None) == ["impl", *HEAD_ARGS, *UNIT, *ARCH]


def test_us8_review_args_principles_with_sha_gets_commit():
    assert review.review_args("principles", RUN, "plan.md", SHA, None) == ["principles", *HEAD_ARGS, "--commit", SHA]


def test_us8_review_args_commit_with_sha_and_base():
    got = review.review_args("commit", RUN, "plan.md", SHA, "base1")
    assert got == ["commit", *HEAD_ARGS, "--commit", SHA, "--base", "base1"]


def test_us8_review_args_answers_ask_with_base_gets_base():
    got = review.review_args("answers-ask", RUN, "plan.md", None, "dev")
    assert got[0] == "answers-ask"
    assert got[1:1 + len(HEAD_ARGS)] == HEAD_ARGS
    assert got[got.index("--base") + 1] == "dev"
    assert "--commit" not in got
    contexts = [got[i + 1] for i, a in enumerate(got) if a == "--context-file"]
    assert contexts == ["/runs/p/t/decisions.tsv"]


def test_us8_review_args_pr_with_base():
    assert review.review_args("pr", RUN, "plan.md", None, "dev") == ["pr", *HEAD_ARGS, "--base", "dev"]


def test_us8_review_args_plan_name_is_joined_to_run():
    got = review.review_args("principles", RUN, "plan-phase-a.md", None, None)
    assert got == ["principles", *HEAD_ARGS[:2], "--plan-file", "/runs/p/t/plan-phase-a.md", *HEAD_ARGS[4:]]


def test_us8_review_args_satisfy_codex_review_required():
    cases = [
        ("tests", None, None),
        ("impl", None, None),
        ("principles", SHA, None),
        ("commit", SHA, "b"),
        ("answers-ask", None, "b"),
        ("pr", None, "b"),
    ]
    for name, commit, base in cases:
        args = review.review_args(name, RUN, "plan.md", commit, base)
        assert args[0] == name
        assert codex_review.missing_args(name, _given(args)) == [], name


STDERR = "warning: something\nother line\nsaved: /runs/p/t/review-commit-3.md\n"


def test_us8_saved_path_reads_real_stderr_format():
    assert review.saved_path(STDERR) == Path("/runs/p/t/review-commit-3.md")


def test_us8_saved_path_takes_the_last_saved_line():
    err = "saved: /a/review-tests-1.md\nnoise\nsaved: /a/review-tests-2.md\n"
    assert review.saved_path(err) == Path("/a/review-tests-2.md")


def test_us8_saved_path_empty_is_none():
    assert review.saved_path("") is None


US8_SOURCE = "def f(a, b):\n    return a + b\n"
US8_IDS = ["C1", "C2", "C3"]


def _us8_review(c2: str) -> str:
    return f"C1: PASS — Fine.\n{c2}\nC3: N/A — Not relevant.\n"


def test_us8_fail_with_quote_in_source_is_kept() -> None:
    text = _us8_review("C2: FAIL — The diff does X. Exact line: `def f(a, b):`")
    assert review.dropped_fails(text, US8_SOURCE) == []


def test_us8_fail_quote_matches_whitespace_normalised() -> None:
    text = _us8_review("C2: FAIL — The diff does X. Exact line: `def  f(a,\n b):`")
    assert review.dropped_fails(text, US8_SOURCE) == []


def test_us8_fail_with_quote_not_in_source_is_dropped() -> None:
    text = _us8_review("C2: FAIL — The diff does X. Exact line: `def g(z):`")
    assert review.dropped_fails(text, US8_SOURCE) == ["C2"]


def test_us8_fail_without_backticks_is_dropped() -> None:
    text = _us8_review("C2: FAIL — The diff does X and it is wrong.")
    assert review.dropped_fails(text, US8_SOURCE) == ["C2"]


def test_us8_quote_on_continuation_line_counts() -> None:
    text = _us8_review("C2: FAIL — The diff does X.\n  Exact line: `def f(a, b):`")
    assert review.dropped_fails(text, US8_SOURCE) == []


def test_us8_quote_in_next_criterion_does_not_count() -> None:
    text = "C1: FAIL — No quote here.\nC2: PASS — See `def f(a, b):`.\n"
    assert review.dropped_fails(text, US8_SOURCE) == ["C1"]


def test_us8_dropped_fails_lists_only_fails_in_order() -> None:
    text = ("C1: FAIL — no quote\nC2: PASS — nothing\nC3: FAIL — `missing line`\n"
            "C4: N/A — nothing\nC5: FAIL — `def f(a, b):`\n")
    assert review.dropped_fails(text, US8_SOURCE) == ["C1", "C3"]


def test_us8_pass_and_na_never_dropped() -> None:
    text = "C1: PASS — no quote\nC2: N/A — no quote\n"
    assert review.dropped_fails(text, US8_SOURCE) == []


def test_us8_derive_verdict_unquoted_fail_gives_pass() -> None:
    text = _us8_review("C2: FAIL — The diff does X, no quote.")
    assert review.derive_verdict(text, US8_IDS, US8_SOURCE) == ("PASS", [])


def test_us8_derive_verdict_quoted_fail_gives_changes() -> None:
    text = _us8_review("C2: FAIL — The diff does X. Exact line: `def f(a, b):`")
    assert review.derive_verdict(text, US8_IDS, US8_SOURCE) == ("CHANGES", ["C2"])


def test_us8_derive_verdict_keeps_only_quoted_fails() -> None:
    text = "C1: FAIL — no quote\nC2: FAIL — `def f(a, b):`\nC3: FAIL — `nope`\n"
    assert review.derive_verdict(text, US8_IDS, US8_SOURCE) == ("CHANGES", ["C2"])


def test_us8_derive_verdict_without_source_keeps_unquoted_fail() -> None:
    text = _us8_review("C2: FAIL — The diff does X, no quote.")
    assert review.derive_verdict(text, US8_IDS) == ("CHANGES", ["C2"])
    assert review.derive_verdict(text, US8_IDS, None) == ("CHANGES", ["C2"])


def test_us8_derive_verdict_source_still_malformed_when_id_missing() -> None:
    text = "C1: PASS — ok\n"
    assert review.derive_verdict(text, US8_IDS, US8_SOURCE) == ("MALFORMED", [])


def test_us8_expected_ids_tests_pass_is_workspace_rubric(tmp_path):
    assert review.expected_ids("tests", tmp_path) == ["T1", "T2", "T3", "T4"]


def test_us8_expected_ids_project_rubric_overrides(tmp_path):
    own = tmp_path / ".claude" / "review-passes"
    own.mkdir(parents=True)
    (own / "tests.md").write_text("- Z1. one thing.\n- Z2. another.\n")
    assert review.expected_ids("tests", tmp_path) == ["Z1", "Z2"]


def test_us8_review_args_answers_ask_carries_decisions_tsv():
    got = review.review_args("answers-ask", RUN, "plan.md", None, None)
    assert got[got.index("--context-file") :][:2] == ["--context-file", "/runs/p/t/decisions.tsv"]


def test_us8_review_args_tests_carries_red_json_and_unit_md():
    got = review.review_args("tests", RUN, "plan.md", None, None)
    pairs = [got[i + 1] for i, a in enumerate(got) if a == "--context-file"]
    assert sorted(pairs) == ["/runs/p/t/red.json", "/runs/p/t/unit.md"]
