"""US-10: the red_run and verify autonodes decide by code."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "workflow"))

import autonodes  # noqa: E402
import graph  # noqa: E402
import state as st  # noqa: E402

ADDED = ["tests/test_a.py::test_one", "tests/test_a.py::test_two"]


def make_ctx(tmp_path, tests=None, touched=None, diff=None, size=None):
    calls = []

    def run_tests(repo, ids):
        calls.append(list(ids))
        return (tests or (lambda ids: {"code": 0, "failed": []}))(ids)

    def unused(*a, **k):
        raise AssertionError("unexpected call")

    extra = {"size": size} if size is not None else {}
    ctx = autonodes.Ctx(
        run=tmp_path,
        repo=tmp_path / "repo",
        python=Path(sys.executable),
        start_review=unused,
        collect_review=unused,
        run_review=unused,
        tests=run_tests,
        touched=touched or (lambda repo: []),
        source=unused,
        commit=unused,
        evidence=unused,
        diff=(lambda repo: diff) if diff is not None else unused,
        file_at=unused,
        log=lambda *a, **k: None,
        now=lambda: "T",
        **extra,
    )
    return ctx, calls


def make_state(claimed_failed=None, reason=True, disputed=None, added=ADDED):
    s = st.new_state("t", "b", "l")
    s = {**s, "node": "red_run"}
    s = st.with_entry(
        s,
        {
            "node": "qa_write",
            "outcome": "recorded",
            "result": {
                "tests_added": added,
                "red_run": {
                    "failed": claimed_failed if claimed_failed is not None else added,
                    "reason_expected": reason,
                },
            },
        },
        "T0",
    )
    impl = {"files": {}, "tests_run": {"passed": 1, "failed": []}}
    if disputed is not None:
        impl["tests_disputed"] = disputed
    return st.with_entry(s, {"node": "implement", "outcome": "recorded", "result": impl}, "T1")


def unit_md(tmp_path, extra=""):
    (tmp_path / "unit.md").write_text("### 3. Thing (US-10)\n" + extra)


def test_us10_red_run_expected_when_all_added_tests_fail(tmp_path):
    ctx, calls = make_ctx(tmp_path, tests=lambda ids: {"code": 1, "failed": list(ADDED)})
    outcome, _, _ = autonodes.HANDLERS["red_run"](make_state(), ctx)
    assert outcome == "expected"
    assert calls == [ADDED]
    red = json.loads((tmp_path / "red.json").read_text())
    assert red["failed"] == ADDED


def test_us10_red_run_unexpected_when_one_added_test_passes_despite_claim(tmp_path):
    ctx, _ = make_ctx(tmp_path, tests=lambda ids: {"code": 1, "failed": [ADDED[0]]})
    outcome, _, _ = autonodes.HANDLERS["red_run"](make_state(), ctx)
    assert outcome == "unexpected"


def test_us10_red_run_unexpected_when_qa_reason_not_expected(tmp_path):
    ctx, _ = make_ctx(tmp_path, tests=lambda ids: {"code": 1, "failed": list(ADDED)})
    outcome, _, _ = autonodes.HANDLERS["red_run"](make_state(reason=False), ctx)
    assert outcome == "unexpected"


def test_us10_verify_tests_touched_even_when_suite_green(tmp_path):
    unit_md(tmp_path, "Lane: fast\n")
    ctx, _ = make_ctx(tmp_path, touched=lambda repo: ["tests/test_a.py"])
    outcome, _, _ = autonodes.HANDLERS["verify"](make_state(disputed=[]), ctx)
    assert outcome == "tests_touched"


def test_us10_verify_failure_listed_in_breaks_gives_lane(tmp_path):
    unit_md(tmp_path, "Lane: fast\nBreaks: tests/test_old.py::test_x\n")
    ctx, calls = make_ctx(tmp_path, tests=lambda ids: {"code": 1, "failed": ["tests/test_old.py::test_x"]})
    outcome, _, _ = autonodes.HANDLERS["verify"](make_state(disputed=[]), ctx)
    assert outcome == "fast"
    assert calls == [[]]


def test_us10_verify_failure_outside_breaks_fails(tmp_path):
    unit_md(tmp_path, "Lane: fast\nBreaks: tests/test_old.py::test_x\n")
    ctx, _ = make_ctx(tmp_path, tests=lambda ids: {"code": 1, "failed": ["tests/test_other.py::test_y"]})
    outcome, _, _ = autonodes.HANDLERS["verify"](make_state(disputed=[]), ctx)
    assert outcome == "fail"


def test_us10_verify_added_test_failing_fails(tmp_path):
    unit_md(tmp_path, "Lane: fast\nBreaks: tests/test_a.py::test_one\n")
    ctx, _ = make_ctx(tmp_path, tests=lambda ids: {"code": 1, "failed": [ADDED[0]]})
    outcome, _, _ = autonodes.HANDLERS["verify"](make_state(disputed=[]), ctx)
    assert outcome == "fail"


def test_us10_verify_disputed_test_fails(tmp_path):
    unit_md(tmp_path, "Lane: fast\n")
    ctx, _ = make_ctx(tmp_path)
    outcome, _, _ = autonodes.HANDLERS["verify"](make_state(disputed=[ADDED[1]]), ctx)
    assert outcome == "fail"


def test_us10_verify_fast_unit_green_gives_fast(tmp_path):
    unit_md(tmp_path, "Lane: fast\n")
    ctx, _ = make_ctx(tmp_path)
    outcome, _, _ = autonodes.HANDLERS["verify"](make_state(disputed=[]), ctx)
    assert outcome == "fast"


def test_us10_verify_full_unit_green_gives_full(tmp_path):
    unit_md(tmp_path, "Lane: full\n")
    ctx, _ = make_ctx(tmp_path)
    outcome, _, _ = autonodes.HANDLERS["verify"](make_state(disputed=[]), ctx)
    assert outcome == "full"


def test_us10_verify_defaults_to_full_without_lane(tmp_path):
    unit_md(tmp_path)
    ctx, _ = make_ctx(tmp_path)
    outcome, _, _ = autonodes.HANDLERS["verify"](make_state(disputed=[]), ctx)
    assert outcome == "full"


def test_us10_red_run_expected_when_added_is_a_file_and_its_tests_fail(tmp_path):
    ctx, _ = make_ctx(tmp_path, tests=lambda ids: {"code": 1, "failed": list(ADDED)})
    outcome, _, _ = autonodes.HANDLERS["red_run"](make_state(added=["tests/test_a.py"]), ctx)
    assert outcome == "expected"



def test_us10_every_auto_node_has_a_handler():
    auto = [n for n in graph.EDGES if graph.kind(n) == "auto"]
    assert [n for n in auto if n not in autonodes.HANDLERS] == []


def test_us10_subtract_check_nothing_when_the_tree_has_no_edits(tmp_path):
    ctx, calls = make_ctx(tmp_path, diff="")
    outcome, _, _ = autonodes.HANDLERS["subtract_check"](make_state(), ctx)
    assert outcome == "nothing"
    assert calls == []


def test_us10_subtract_check_pass_when_tests_untouched_and_suite_green(tmp_path):
    ctx, calls = make_ctx(tmp_path, diff="--- a/src/x.py\n+++ b/src/x.py\n-dead\n")
    outcome, entry, _ = autonodes.HANDLERS["subtract_check"](make_state(), ctx)
    assert outcome == "pass"
    assert calls == [[]]
    assert entry["failed"] == []


def test_us10_subtract_check_fail_when_tests_were_touched(tmp_path):
    ctx, calls = make_ctx(tmp_path, diff="--- a/tests/t.py\n", touched=lambda repo: ["tests/t.py"])
    outcome, entry, _ = autonodes.HANDLERS["subtract_check"](make_state(), ctx)
    assert outcome == "fail"
    assert entry["touched"] == ["tests/t.py"]


def test_us10_subtract_check_fail_when_the_suite_fails(tmp_path):
    red = {"code": 1, "failed": ["tests/t.py::test_a"]}
    ctx, _ = make_ctx(tmp_path, tests=lambda ids: red, diff="--- a/src/x.py\n-dead\n")
    outcome, entry, _ = autonodes.HANDLERS["subtract_check"](make_state(), ctx)
    assert outcome == "fail"
    assert entry["failed"] == ["tests/t.py::test_a"]


def test_us10_full_suite_pass_runs_the_whole_suite(tmp_path):
    ctx, calls = make_ctx(tmp_path)
    outcome, entry, _ = autonodes.HANDLERS["full_suite"](make_state(), ctx)
    assert outcome == "pass"
    assert calls == [[]]
    assert entry["failed"] == []


def test_us10_full_suite_fail_accepts_no_declared_breaks(tmp_path):
    unit_md(tmp_path, "Breaks: tests/t.py::test_a\n")
    ctx, _ = make_ctx(tmp_path, tests=lambda ids: {"code": 1, "failed": ["tests/t.py::test_a"]})
    outcome, entry, _ = autonodes.HANDLERS["full_suite"](make_state(), ctx)
    assert outcome == "fail"
    assert entry["failed"] == ["tests/t.py::test_a"]


SCOPED = "Lane: fast\nEstimate: ~12 lines. Files: `scripts/a.py`, `tests/test_a.py`.\n"


def test_us24_verify_fast_unit_with_file_outside_its_files_gives_full_with_reason(tmp_path):
    unit_md(tmp_path, SCOPED)
    ctx, _ = make_ctx(tmp_path, size=lambda repo: {"scripts/a.py": 5, "scripts/other.py": 3})
    outcome, entry, _ = autonodes.HANDLERS["verify"](make_state(disputed=[]), ctx)
    assert outcome == "full"
    assert entry == {"failed": [], "disputed": [], "touched": [], "reasons": ["outside: scripts/other.py"]}


def test_us24_verify_fast_unit_over_its_limit_gives_full_with_reason(tmp_path):
    unit_md(tmp_path, SCOPED)
    ctx, _ = make_ctx(tmp_path, size=lambda repo: {"scripts/a.py": 31})
    outcome, entry, _ = autonodes.HANDLERS["verify"](make_state(disputed=[]), ctx)
    assert outcome == "full"
    assert entry["reasons"] == ["size: 31 lines, limit 30"]


def test_us24_verify_fast_unit_inside_files_and_limit_gives_fast_with_no_reasons(tmp_path):
    unit_md(tmp_path, SCOPED)
    sizes = []
    ctx, _ = make_ctx(tmp_path, size=lambda repo: sizes.append(repo) or {"scripts/a.py": 12})
    outcome, entry, _ = autonodes.HANDLERS["verify"](make_state(disputed=[]), ctx)
    assert outcome == "fast"
    assert entry == {"failed": [], "disputed": [], "touched": [], "reasons": []}
    assert sizes == [tmp_path / "repo"]


def test_us24_verify_full_unit_has_no_reasons_and_does_not_measure(tmp_path):
    unit_md(tmp_path, "Lane: full\nFiles: `scripts/a.py`.\n")

    def boom(repo):
        raise AssertionError("size must not be called")

    ctx, _ = make_ctx(tmp_path, size=boom)
    outcome, entry, _ = autonodes.HANDLERS["verify"](make_state(disputed=[]), ctx)
    assert outcome == "full"
    assert entry == {"failed": [], "disputed": [], "touched": [], "reasons": []}


def test_us24_verify_failing_suite_gives_fail_with_no_reasons(tmp_path):
    unit_md(tmp_path, SCOPED)
    ctx, _ = make_ctx(
        tmp_path,
        tests=lambda ids: {"code": 1, "failed": ["tests/test_o.py::test_x"]},
        size=lambda repo: {"scripts/other.py": 99},
    )
    outcome, entry, _ = autonodes.HANDLERS["verify"](make_state(disputed=[]), ctx)
    assert outcome == "fail"
    assert entry["reasons"] == []
