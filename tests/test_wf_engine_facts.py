"""US-7: engine.decision_facts and engine.legal build decision inputs from the state and run folder."""

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "workflow"))

import engine  # noqa: E402
import state as st  # noqa: E402

CHANGE = "--- a/src/x.py\n+++ b/src/x.py\n@@ -1,2 +1,2 @@\n-def f(a):\n+def f(a, b):\n     return a\n"


def _ctx(tmp_path, diff="", file_at=None):
    return SimpleNamespace(
        run=tmp_path,
        repo=tmp_path,
        diff=lambda r: diff,
        file_at=file_at or (lambda repo, path, sha: f"{path}@{sha}"),
    )


def _state(node, unit=1):
    s = st.new_state("t", "b", "l")
    s["unit"], s["node"] = unit, node
    return s


def _tests_review(s, fails=("T2",)):
    entry = {
        "node": "tests_review",
        "outcome": "CHANGES",
        "reviews": [{"pass": "tests", "fails": list(fails), "verdict": "CHANGES"}],
    }
    return st.with_entry(s, entry, "n")


def test_us7_facts_fails_and_passes_come_from_the_last_review_entry(tmp_path):
    s = _tests_review(_state("tests_decide"))
    f = engine.decision_facts(s, _ctx(tmp_path))
    assert f["fails"] == ["T2"]
    assert f["passes"] == {"T2": "tests"}


def test_us7_facts_read_at_tests_decide_uses_the_head_sha(tmp_path):
    s = _tests_review(_state("tests_decide"))
    s["head"] = "abc123"
    seen = []

    def file_at(repo, path, sha):
        seen.append((repo, path, sha))
        return "body"

    f = engine.decision_facts(s, _ctx(tmp_path, file_at=file_at))
    assert f["read"]("a.py") == "body"
    assert seen == [(tmp_path, "a.py", "abc123")]


def test_us7_facts_read_elsewhere_uses_the_working_tree(tmp_path):
    s = _state("impl_decide")
    s["head"] = "abc123"
    seen = []
    ctx = _ctx(tmp_path, file_at=lambda repo, path, sha: seen.append(sha) or "wt")
    assert engine.decision_facts(s, ctx)["read"]("a.py") == "wt"
    assert seen == [None]


def test_us7_facts_failures_are_the_failed_list_of_the_last_run_entry(tmp_path):
    s = _state("fail_decide")
    s = st.with_entry(s, {"node": "verify", "outcome": "fail", "failed": ["old::t"]}, "n")
    s = st.with_entry(s, {"node": "verify", "outcome": "fail", "failed": ["tests/a.py::t1"]}, "n")
    f = engine.decision_facts(s, _ctx(tmp_path))
    assert "tests/a.py::t1" in f["failures"]
    assert "old::t" not in f["failures"]


def test_us7_facts_docs_hold_plan_and_ask_texts_and_run_is_ctx_run(tmp_path):
    (tmp_path / "plan.md").write_text("PLAN TEXT")
    (tmp_path / "ask.md").write_text("ASK TEXT")
    f = engine.decision_facts(_state("tests_decide"), _ctx(tmp_path))
    assert "PLAN TEXT" in f["docs"]
    assert "ASK TEXT" in f["docs"]
    assert f["run"] == tmp_path


def test_us7_facts_resume_comes_from_pending(tmp_path):
    s = _state("user")
    s["pending"] = {"kind": "user", "resume": ["implement", "commit_fix"]}
    assert engine.decision_facts(s, _ctx(tmp_path))["resume"] == ["implement", "commit_fix"]


def test_us7_facts_uncovered_names_a_changed_signature_without_approved_architecture(tmp_path):
    f = engine.decision_facts(_state("impl_decide"), _ctx(tmp_path, diff=CHANGE))
    assert set(f["uncovered"]) == {"f"}


def test_us7_facts_uncovered_is_empty_when_architecture_is_approved_and_names_it(tmp_path):
    (tmp_path / "architecture.md").write_text("Status: approved\n\nChanges `f` to take b.\n")
    f = engine.decision_facts(_state("impl_decide"), _ctx(tmp_path, diff=CHANGE))
    assert not f["uncovered"]


def test_us7_legal_restricts_to_architecture_stop_for_an_uncovered_signature_change(tmp_path):
    s = _state("impl_decide")
    assert engine.legal(s, _ctx(tmp_path, diff=CHANGE)) == ["architecture_stop"]


def test_us7_legal_is_unrestricted_for_an_empty_diff(tmp_path):
    opts = engine.legal(_state("impl_decide"), _ctx(tmp_path, diff=""))
    assert "correct" in opts
    assert opts != ["architecture_stop"]


def test_us7_legal_ignores_changes_committed_in_an_earlier_unit(tmp_path):
    s = _state("impl_decide", unit=1)
    s = st.with_entry(s, {"node": "commit_fix", "outcome": "done", "diff": CHANGE}, "n")
    s["unit"] = 2
    s["node"] = "impl_decide"
    opts = engine.legal(s, _ctx(tmp_path, diff=""))
    assert "correct" in opts
