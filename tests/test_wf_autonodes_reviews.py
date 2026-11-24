"""US-8: the review autonodes derive verdicts by code from canned Codex reviews."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "workflow"))

import autonodes  # noqa: E402
import state as st  # noqa: E402

RUBRICS = {
    "tests": ["T1", "T2"],
    "impl": ["C1", "C2"],
    "principles": ["P1", "P2", "P3"],
    "alternatives": ["B1"],
}
SOURCE = "def real_function():\n    return 1\n"


def write_rubrics(repo):
    d = repo / ".claude" / "review-passes"
    d.mkdir(parents=True)
    for name, ids in RUBRICS.items():
        (d / f"{name}.md").write_text("\n".join(f"- {i}. Criterion {i}." for i in ids) + "\n")


def review_text(ids, fails=None, verdict="PASS", drop=None):
    fails = fails or {}
    lines = []
    for i in ids:
        if i in fails:
            lines.append(f"{i}: FAIL — problem {fails[i]}")
        else:
            lines.append(f"{i}: PASS — fine")
    return "\n".join(lines) + f"\nVERDICT {verdict}\n"


def make_ctx(tmp_path, texts, collect=None, source=SOURCE, diff=SOURCE):
    """texts: list of review texts handed out in order by run_review (None = nothing saved)."""
    repo = tmp_path / "repo"
    write_rubrics(repo)
    runs, collected = [], []
    queue = list(texts)

    def run_review(args, repo_):
        runs.append(list(args))
        text = queue.pop(0)
        if text is None:
            return None
        path = tmp_path / f"rev{len(runs)}.md"
        path.write_text(text)
        return path

    def collect_review(handle):
        collected.append(handle)
        text = collect
        if text is None:
            return None
        path = tmp_path / "collected.md"
        path.write_text(text)
        return path

    def unused(*a, **k):
        raise AssertionError("unexpected call")

    ctx = autonodes.Ctx(
        run=tmp_path,
        repo=repo,
        python=Path(sys.executable),
        start_review=unused,
        collect_review=collect_review,
        run_review=run_review,
        tests=unused,
        touched=unused,
        source=lambda repo_, commit, base: source,
        commit=unused,
        evidence=unused,
        diff=lambda repo_: diff,
        file_at=unused,
        log=lambda *a, **k: None,
        now=lambda: "T",
    )
    return ctx, runs, collected


def make_state(node):
    s = st.new_state("t", "b", "LAUNCH")
    return {**s, "node": node, "head": "abc123", "review": {"handle": 1}}


def test_us8_verdict_line_is_ignored_when_all_criteria_pass(tmp_path):
    ctx, _, _ = make_ctx(tmp_path, [review_text(RUBRICS["impl"], verdict="CHANGES")])
    outcome, entry, _ = autonodes.HANDLERS["impl_review"](make_state("impl_review"), ctx)
    assert outcome == "PASS"
    assert entry["verdict"] == "PASS"
    assert entry["reviews"][0]["fails"] == []


def test_us8_tests_review_collects_background_review(tmp_path):
    ctx, runs, collected = make_ctx(tmp_path, [], collect=review_text(RUBRICS["tests"]))
    outcome, entry, _ = autonodes.HANDLERS["tests_review"](make_state("tests_review"), ctx)
    assert outcome == "PASS"
    assert collected == [{"handle": 1}]
    assert runs == []
    assert entry["reviews"][0]["pass"] == "tests"


def test_us8_background_review_that_saved_nothing_is_rerun_once(tmp_path):
    ctx, runs, collected = make_ctx(tmp_path, [review_text(RUBRICS["tests"])], collect=None)
    outcome, entry, _ = autonodes.HANDLERS["tests_review"](make_state("tests_review"), ctx)
    assert outcome == "PASS"
    assert len(collected) == 1
    assert len(runs) == 1
    assert entry["verdict"] == "PASS"


def test_us8_two_malformed_reviews_give_malformed(tmp_path):
    bad = review_text(["C1"])
    ctx, runs, _ = make_ctx(tmp_path, [bad, bad])
    outcome, entry, _ = autonodes.HANDLERS["impl_review"](make_state("impl_review"), ctx)
    assert outcome == "MALFORMED"
    assert len(runs) == 2
    assert entry["verdict"] == "MALFORMED"


def test_us8_branch_reviews_quoted_fail_gives_changes_with_base_not_commit(tmp_path):
    principles = review_text(RUBRICS["principles"], fails={"P3": "see `real_function`"})
    ctx, runs, _ = make_ctx(tmp_path, [principles, review_text(RUBRICS["alternatives"])])
    outcome, entry, _ = autonodes.HANDLERS["branch_reviews"](make_state("branch_reviews"), ctx)
    assert outcome == "CHANGES"
    by_pass = {r["pass"]: r for r in entry["reviews"]}
    assert by_pass["principles"]["fails"] == ["P3"]
    assert by_pass["principles"]["verdict"] == "CHANGES"
    assert by_pass["alternatives"]["fails"] == []
    assert entry["verdict"] == "CHANGES"
    assert len(runs) == 2
    for args in runs:
        assert args[args.index("--base") + 1] == "LAUNCH"
        assert "--commit" not in args


def test_us8_unquoted_fail_is_dropped_and_verdict_passes(tmp_path):
    ctx, _, _ = make_ctx(tmp_path, [review_text(RUBRICS["impl"], fails={"C2": "see `not_in_source`"})])
    outcome, entry, _ = autonodes.HANDLERS["impl_review"](make_state("impl_review"), ctx)
    assert outcome == "PASS"
    assert entry["reviews"][0]["dropped"] == ["C2"]
    assert entry["reviews"][0]["fails"] == []


def test_us18_decided_tests_review_is_not_asked_again(tmp_path):
    ctx, runs, collected = make_ctx(tmp_path, [], collect=review_text(RUBRICS["tests"], fails={"T1": 1}))
    state = make_state("tests_review")
    for entry in (
        {"node": "commit_tests", "outcome": "done", "sha": "abc123"},
        {"node": "tests_review", "outcome": "CHANGES", "verdict": "CHANGES", "reviews": []},
        {"node": "tests_decide", "decision": "overstated"},
    ):
        state = st.with_entry(state, entry, "T")
    outcome, entry, _ = autonodes.HANDLERS["tests_review"](state, ctx)
    assert outcome == "PASS"
    assert entry == {"verdict": "PASS", "reviews": [], "decided": True}
    assert collected == []
    assert runs == []


def test_us18_impl_review_args_have_neither_commit_nor_base(tmp_path):
    ctx, runs, _ = make_ctx(tmp_path, [review_text(RUBRICS["impl"])])
    autonodes.HANDLERS["impl_review"](make_state("impl_review"), ctx)
    assert len(runs) == 1
    assert "--commit" not in runs[0]
    assert "--base" not in runs[0]


def test_us18_impl_review_keeps_fail_quoting_uncommitted_change(tmp_path):
    ctx, _, _ = make_ctx(
        tmp_path,
        [review_text(RUBRICS["impl"], fails={"C2": "see `only_in_working_tree`"})],
        source="def only_in_head():\n    return 1\n",
        diff="def only_in_working_tree():\n    return 2\n",
    )
    outcome, entry, _ = autonodes.HANDLERS["impl_review"](make_state("impl_review"), ctx)
    assert outcome == "CHANGES"
    assert entry["reviews"][0]["fails"] == ["C2"]
    assert entry["reviews"][0]["dropped"] == []


def test_us18_impl_review_drops_fail_quoting_only_the_head_commit(tmp_path):
    ctx, _, _ = make_ctx(
        tmp_path,
        [review_text(RUBRICS["impl"], fails={"C2": "see `only_in_head`"})],
        source="def only_in_head():\n    return 1\n",
        diff="def only_in_working_tree():\n    return 2\n",
    )
    outcome, entry, _ = autonodes.HANDLERS["impl_review"](make_state("impl_review"), ctx)
    assert outcome == "PASS"
    assert entry["reviews"][0]["fails"] == []
    assert entry["reviews"][0]["dropped"] == ["C2"]
