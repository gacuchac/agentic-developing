"""Tests for the commit nodes of scripts/workflow/autonodes.py."""

import json
from pathlib import Path

import autonodes
import pytest
import state as st

UNIT_MD = "### 3. Do the thing (US-9)\nLane: fast\n"
SHA = "abc1234"


def _make(tmp_path, touched=("tests/test_x.py",), commit_raises=False):
    calls = {"commit": [], "log": [], "start_review": [], "evidence": []}

    def commit(repo, message, paths):
        calls["commit"].append((repo, message, paths))
        if commit_raises:
            raise RuntimeError("hook said no")
        return SHA

    def start_review(args, repo, log):
        calls["start_review"].append((args, repo, log))
        return {"pid": 42, "log": str(log)}

    def evidence(repo, run, sha, python):
        calls["evidence"].append((repo, run, sha, python))
        return {"sha": sha, "ok": True}

    def unused(*a, **k):
        raise AssertionError("unexpected call")

    ctx = autonodes.Ctx(
        run=tmp_path,
        repo=tmp_path / "repo",
        python=tmp_path / "py",
        start_review=start_review,
        collect_review=unused,
        run_review=unused,
        tests=unused,
        touched=lambda repo: list(touched),
        source=unused,
        commit=commit,
        evidence=evidence,
        diff=unused,
        file_at=unused,
        log=lambda run, cells: calls["log"].append((run, cells)),
        now=lambda: "2026-01-01T00:00:00",
    )
    (tmp_path / "unit.md").write_text(UNIT_MD)
    state = st.new_state("t", "feature/x", "launchsha")
    state["head"] = "oldhead"
    return ctx, state, calls


def test_us10_commit_tests_commits_only_touched_paths(tmp_path):
    ctx, state, calls = _make(tmp_path, touched=("tests/a.py", "tests/b.py"))
    outcome, entry, new = autonodes.HANDLERS["commit_tests"](state, ctx)
    assert outcome == "done"
    assert len(calls["commit"]) == 1
    _, message, paths = calls["commit"][0]
    assert message == "test(US-9): Do the thing"
    assert list(paths) == ["tests/a.py", "tests/b.py"]
    assert entry == {"sha": SHA, "message": "test(US-9): Do the thing"}
    assert new["head"] == SHA
    assert calls["log"] and calls["log"][0][0] == tmp_path


def test_us10_commit_tests_starts_one_review_and_stores_handle(tmp_path):
    ctx, state, calls = _make(tmp_path)
    _, _, new = autonodes.HANDLERS["commit_tests"](state, ctx)
    assert len(calls["start_review"]) == 1
    assert calls["start_review"][0][1] == ctx.repo
    assert new["review"] == {"pid": 42, "log": str(calls["start_review"][0][2])}


def test_us10_commit_tests_without_test_paths_is_refused(tmp_path):
    ctx, state, calls = _make(tmp_path, touched=())
    outcome, _, new = autonodes.HANDLERS["commit_tests"](state, ctx)
    assert outcome == "refused"
    assert calls["commit"] == []
    assert calls["start_review"] == []
    assert new["head"] == "oldhead"


def test_us10_commit_fix_commits_everything_and_writes_evidence(tmp_path):
    ctx, state, calls = _make(tmp_path)
    outcome, entry, new = autonodes.HANDLERS["commit_fix"](state, ctx)
    assert outcome == "done"
    _, message, paths = calls["commit"][0]
    assert message == "US-9: Do the thing"
    assert paths is None
    assert new["head"] == SHA
    assert calls["evidence"] == [(ctx.repo, tmp_path, SHA, ctx.python)]
    ev_path = tmp_path / f"evidence-{SHA}.json"
    assert json.loads(ev_path.read_text()) == {"sha": SHA, "ok": True}
    assert entry["sha"] == SHA
    assert entry["message"] == "US-9: Do the thing"
    assert Path(entry["evidence"]) == ev_path
    assert len(calls["log"]) == 1


def test_us10_commit_subtract_message_uses_stories_and_summary(tmp_path):
    ctx, state, calls = _make(tmp_path)
    state["history"].append({"node": "subtract", "result": {"removed": "dead helper", "files": {"a.py": 3}}})
    outcome, entry, new = autonodes.HANDLERS["commit_subtract"](state, ctx)
    assert outcome == "done"
    _, message, paths = calls["commit"][0]
    assert message == "US-9: Subtract: dead helper"
    assert paths is None
    assert entry["sha"] == SHA and entry["message"] == message
    assert (tmp_path / f"evidence-{SHA}.json").exists()
    assert new["head"] == SHA
    assert len(calls["log"]) == 1


@pytest.mark.parametrize("node", ["commit_tests", "commit_fix", "commit_subtract"])
def test_us10_commit_hook_refusal_gives_refused_with_error(tmp_path, node):
    ctx, state, calls = _make(tmp_path, commit_raises=True)
    state["history"].append({"node": "subtract", "result": {"removed": "x", "files": {}}})
    before = json.loads(json.dumps(state))
    outcome, entry, new = autonodes.HANDLERS[node](state, ctx)
    assert outcome == "refused"
    assert entry["error"] == "hook said no"
    assert entry["message"]
    assert "sha" not in entry
    assert new == before
    assert calls["log"] == []


def test_us10_commit_tests_review_args_name_the_new_commit(tmp_path):
    ctx, state, calls = _make(tmp_path)
    autonodes.HANDLERS["commit_tests"](state, ctx)
    args = calls["start_review"][0][0]
    assert args[0] == "tests"
    assert args[args.index("--commit") + 1] == SHA
