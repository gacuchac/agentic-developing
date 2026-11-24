"""US-11: wf status and report text say where the task is and what was decided."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "workflow"))

import wf  # noqa: E402

HEADER = "ts\tphase\tdecision\twhy\tevidence\tresult"


def _state(n=8, pending=None, last_extra=None):
    history = [{"node": f"marker{i}node", "outcome": "done", "to": f"dest{i}", "t": "t", "unit": "3"} for i in range(n)]
    if last_extra:
        history[-1].update(last_extra)
    return {
        "task": "my-task",
        "mode": "sequential",
        "stage": "build",
        "unit": 3,
        "fix": 0,
        "node": "verify",
        "round": 2,
        "pending": pending or {"kind": "auto"},
        "history": history,
    }


def _section(text, title):
    parts = text.split("## ")
    for p in parts:
        if p.startswith(title):
            return p
    return ""


def test_us11_status_names_node_and_pending_step_id():
    st = _state(pending={"kind": "agent", "agent": "reviewer", "step_id": "step-77"})
    out = wf.status_text(st)
    assert "my-task" in out and "sequential" in out and "build" in out
    assert "verify" in out
    assert "reviewer" in out and "step-77" in out


def test_us11_status_shows_only_last_five_history_entries():
    out = wf.status_text(_state(n=8))
    for i in (0, 1, 2):
        assert f"marker{i}node" not in out
    for i in (3, 4, 5, 6, 7):
        assert f"marker{i}node" in out
    assert "dest7" in out


def test_us11_status_shows_error_of_last_entry_when_pending():
    st = _state(
        pending={"kind": "agent", "agent": "reviewer", "step_id": "s1"}, last_extra={"error": "boom-bad-evidence"}
    )
    assert "boom-bad-evidence" in wf.status_text(st)


def test_us11_report_wrong_dismissal_in_decisions_and_dismissals():
    log = "\n".join(
        [
            HEADER,
            "t1\tu3 tests_decide\tapproved\tfine\t\tverify",
            "t2\tu3 tests_decide\twrong\tquoteXYZ = 1\tT1\tverify",
            "",
        ]
    )
    out = wf.report_text(log)
    assert "quoteXYZ = 1" in _section(out, "Decisions")
    dis = _section(out, "Dismissals")
    assert "quoteXYZ = 1" in dis
    assert "fine" not in dis


def test_us11_report_commit_row_shows_sha_under_commits():
    log = "\n".join(
        [
            HEADER,
            "t1\tu3 commit_fix\tdone\tUS-1: do it\tabc1234\tnext_unit",
            "t2\tu3 verify\tdone\tchecked\tzzz9999\tnext",
            "",
        ]
    )
    com = _section(wf.report_text(log), "Commits")
    assert "abc1234" in com
    assert "zzz9999" not in com


def test_us11_report_ratchet_candidates_only_ids_dismissed_twice():
    log = "\n".join(
        [
            HEADER,
            "t1\tu1 tests_decide\twrong\tq1\tT2\tverify",
            "t2\tu2 tests_decide\toverstated\tq2\tT2; T9\tverify",
            "",
        ]
    )
    rat = _section(wf.report_text(log), "Ratchet candidates")
    assert "T2" in rat
    assert "T9" not in rat


def _review_entry(dropped):
    review = {"pass": "alternatives", "review": "/runs/t/review-alternatives-1.md", "verdict": "PASS",
              "fails": [], "dropped": dropped}
    return {"node": "branch_reviews", "outcome": "PASS", "to": "full_suite", "t": "t", "unit": "3",
            "verdict": "PASS", "reviews": [review]}


def test_us18_dropped_text_names_pass_ids_and_review_file():
    state = {**_state(), "history": [_review_entry(["L1"])]}
    assert wf.dropped_text(state) == "dropped: alternatives L1 (review-alternatives-1.md)"


def test_us18_dropped_text_is_empty_when_nothing_dropped():
    state = {**_state(), "history": [_review_entry([])]}
    assert wf.dropped_text(state) == ""
