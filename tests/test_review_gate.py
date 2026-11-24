import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

_path = Path(__file__).resolve().parents[1] / "scripts" / "hooks" / "review_gate.py"
_spec = importlib.util.spec_from_file_location("review_gate", _path)
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)

WS_NAMES = ["Developing", "other-ws"]


def _ws(tmp_path, name):
    return tmp_path / "deep" / name


def test_us2_task_id_strips_feature_and_hotfix_prefix():
    assert gate.task_id("feature/x") == "x"
    assert gate.task_id("hotfix/a-b") == "a-b"
    assert gate.task_id("bugfix/y") == "y"


def test_us2_task_id_is_none_for_non_task_branches():
    assert gate.task_id("dev") is None
    assert gate.task_id("feat/x") is None


@pytest.mark.parametrize("name", WS_NAMES)
def test_us2_run_folder_for_project(tmp_path, name):
    ws = _ws(tmp_path, name)
    got = gate.run_folder(ws / "proj" / ".git", "t", ws)
    assert got == ws / ".claude" / "runs" / "proj" / "t"


@pytest.mark.parametrize("name", WS_NAMES)
def test_us2_run_folder_for_workspace_itself(tmp_path, name):
    ws = _ws(tmp_path, name)
    got = gate.run_folder(ws / ".git", "t", ws)
    assert got == ws / ".claude" / "runs" / name / "t"


@pytest.mark.parametrize("name", WS_NAMES)
def test_us2_run_folder_for_worktree_same_common_dir_as_project(tmp_path, name):
    # A worktree's `git rev-parse --git-common-dir` is the main repo's .git,
    # so it is the same input as the project case.
    ws = _ws(tmp_path, name)
    assert gate.run_folder(ws / "proj" / ".git", "t", ws) == ws / ".claude" / "runs" / "proj" / "t"


@pytest.mark.parametrize("name", WS_NAMES)
def test_us2_run_folder_none_outside_workspace(tmp_path, name):
    ws = _ws(tmp_path, name)
    assert gate.run_folder(tmp_path / "elsewhere" / "repo" / ".git", "t", ws) is None


@pytest.mark.parametrize("name", WS_NAMES)
def test_us2_run_folder_none_for_nested_repo(tmp_path, name):
    ws = _ws(tmp_path, name)
    assert gate.run_folder(ws / "a" / "b" / ".git", "t", ws) is None


SHA = "a" * 40


def _header(pass_name, sha):
    return f"<!-- pass: {pass_name} | model: m | base: commit {sha} | exit: 0 | 2026-01-01 00:00:00 -->\nbody\n"


def test_us2_reviewed_true_for_commit_review_with_sha(tmp_path):
    (tmp_path / "review-commit-1.md").write_text(_header("commit", SHA))
    assert gate.reviewed(tmp_path, SHA) is True


def test_us2_reviewed_false_for_other_sha(tmp_path):
    (tmp_path / "review-commit-1.md").write_text(_header("commit", "b" * 40))
    assert gate.reviewed(tmp_path, SHA) is False


def test_us2_reviewed_false_for_sha_prefix_only(tmp_path):
    (tmp_path / "review-commit-1.md").write_text(_header("commit", SHA[:12]))
    assert gate.reviewed(tmp_path, SHA) is False


def test_us2_reviewed_false_for_principles_review(tmp_path):
    (tmp_path / "review-principles-1.md").write_text(_header("principles", SHA))
    assert gate.reviewed(tmp_path, SHA) is False


def test_us2_reviewed_false_for_empty_or_missing_folder(tmp_path):
    assert gate.reviewed(tmp_path, SHA) is False
    assert gate.reviewed(tmp_path / "missing", SHA) is False


def _git(*args):
    subprocess.run(["git", *args], check=True, capture_output=True)


def _commit(name):
    Path(name).write_text(name)
    _git("add", name)
    _git("commit", "-m", name)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _git("init", "-b", "dev")
    _git("config", "user.name", "t")
    _git("config", "user.email", "t@example.com")
    _git("config", "commit.gpgsign", "false")
    _commit("base")
    _git("checkout", "-b", "feature/x")
    return tmp_path


def test_us2_needs_review_false_right_after_branching(repo):
    assert gate.needs_review(repo) is False


def test_us2_needs_review_true_after_one_commit_on_branch(repo):
    _commit("own")
    assert gate.needs_review(repo) is True


def test_us2_needs_review_false_when_head_is_merge_of_dev(repo):
    _commit("own")
    _git("checkout", "dev")
    _commit("newdev")
    _git("checkout", "feature/x")
    _git("merge", "--no-ff", "-m", "merge dev", "dev")
    assert gate.needs_review(repo) is False


def test_us2_needs_review_true_when_repo_has_no_dev(repo):
    _git("branch", "-m", "dev", "main")
    _commit("own")
    assert gate.needs_review(repo) is True


def test_us2_needs_review_uses_repo_arg_not_cwd(repo, tmp_path_factory, monkeypatch):
    _commit("own")
    elsewhere = tmp_path_factory.mktemp("elsewhere")
    monkeypatch.chdir(elsewhere)
    assert gate.needs_review(repo) is True


@pytest.fixture
def ws_project(tmp_path, monkeypatch):
    ws = tmp_path.resolve() / "Developing"
    proj = ws / "proj"
    proj.mkdir(parents=True)
    monkeypatch.chdir(proj)
    _git("init", "-b", "dev")
    _git("config", "user.name", "t")
    _git("config", "user.email", "t@example.com")
    _git("config", "commit.gpgsign", "false")
    _commit("base")
    _git("checkout", "-b", "feature/x")
    return ws


def _short():
    out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], check=True, capture_output=True, text=True)
    return out.stdout.strip()


def _save_review(ws, short, task="x"):
    folder = ws / ".claude" / "runs" / "proj" / task
    folder.mkdir(parents=True)
    (folder / "review-commit-1.md").write_text(
        f"<!-- pass: commit | model: m | base: commit {short} | exit: 0 | 2026-01-01 00:00:00 -->\nVERDICT: FAIL\n"
    )


def test_us6_gate_blocks_unreviewed_head_commit(ws_project, capsys):
    _commit("own")
    assert gate.main(ws_project) == 1
    err = capsys.readouterr().err
    assert "Commit blocked" in err
    assert _short() in err
    assert "feature/x" in err


def test_us6_gate_passes_when_head_commit_is_reviewed(ws_project):
    _commit("own")
    _save_review(ws_project, _short())
    assert gate.main(ws_project) == 0


def test_us6_gate_blocks_when_only_an_older_commit_is_reviewed(ws_project):
    _commit("own")
    _save_review(ws_project, _short())
    _commit("second")
    assert gate.main(ws_project) == 1


def test_us6_gate_passes_first_commit_on_fresh_branch(ws_project):
    assert gate.main(ws_project) == 0


def test_us6_gate_passes_on_non_task_branch(ws_project):
    _git("checkout", "-b", "scratch")
    _commit("own")
    assert gate.main(ws_project) == 0


def test_us6_gate_passes_when_head_is_merge_commit(ws_project):
    _commit("own")
    _git("checkout", "dev")
    _commit("newdev")
    _git("checkout", "feature/x")
    _git("merge", "--no-ff", "-m", "merge dev", "dev")
    assert gate.main(ws_project) == 0


def test_us6_gate_passes_when_repo_is_outside_workspace(ws_project, tmp_path):
    _commit("own")
    assert gate.main(tmp_path / "other-workspace") == 0


def _header_exit(sha, code):
    return f"<!-- pass: commit | model: m | base: commit {sha} | exit: {code} | 2026-01-01 00:00:00 -->\nVERDICT: PASS\n"


def _save_review_exit(ws, short, code, task="x"):
    folder = ws / ".claude" / "runs" / "proj" / task
    folder.mkdir(parents=True)
    (folder / "review-commit-1.md").write_text(_header_exit(short, code))


def test_x12_reviewed_false_when_codex_exit_nonzero(tmp_path):
    (tmp_path / "review-commit-1.md").write_text(_header_exit(SHA, 1))
    assert gate.reviewed(tmp_path, SHA) is False


def test_x12_reviewed_false_when_exit_is_ten_not_zero(tmp_path):
    (tmp_path / "review-commit-1.md").write_text(_header_exit(SHA, 10))
    assert gate.reviewed(tmp_path, SHA) is False


def test_x12_reviewed_true_when_exit_zero_even_if_verdict_changes(tmp_path):
    (tmp_path / "review-commit-1.md").write_text(_header_exit(SHA, 0).replace("PASS", "CHANGES"))
    assert gate.reviewed(tmp_path, SHA) is True


def test_x12_reviewed_true_when_one_of_two_reviews_succeeded(tmp_path):
    (tmp_path / "review-commit-1.md").write_text(_header_exit(SHA, 1))
    (tmp_path / "review-commit-2.md").write_text(_header_exit(SHA, 0))
    assert gate.reviewed(tmp_path, SHA) is True


def test_x12_gate_blocks_head_whose_review_failed(ws_project):
    _commit("own")
    _save_review_exit(ws_project, _short(), 1)
    assert gate.main(ws_project) == 1


def test_x12_gate_passes_head_whose_review_succeeded(ws_project):
    _commit("own")
    _save_review_exit(ws_project, _short(), 0)
    assert gate.main(ws_project) == 0


def _commit_deleting(name):
    _git("rm", name)
    _git("commit", "-m", f"delete {name}")


def _commit_skill(path):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(path)
    _git("add", path)
    _git("commit", "-m", path)


def test_x12_gate_passes_deletion_only_head_without_review(ws_project):
    _commit("own")
    _commit_deleting("own")
    assert gate.main(ws_project) == 0


def test_x12_gate_passes_skills_only_head_without_review(ws_project):
    _commit("own")
    _commit_skill(".claude/skills/s/SKILL.md")
    assert gate.main(ws_project) == 0


def test_x12_gate_blocks_head_mixing_deletion_and_edit(ws_project):
    _commit("own")
    Path("extra").write_text("x")
    _git("add", "extra")
    _git("rm", "own")
    _git("commit", "-m", "mixed")
    assert gate.main(ws_project) == 1


def test_x12_gate_blocks_head_mixing_skills_and_other_file(ws_project):
    _commit("own")
    Path("other").write_text("x")
    Path(".claude/skills/s").mkdir(parents=True)
    Path(".claude/skills/s/SKILL.md").write_text("x")
    _git("add", "other", ".claude/skills/s/SKILL.md")
    _git("commit", "-m", "mixed")
    assert gate.main(ws_project) == 1


def test_x12_nothing_to_review_true_for_deletion_only(ws_project):
    _commit("own")
    _commit_deleting("own")
    assert gate.nothing_to_review(Path.cwd()) is True


def test_x12_nothing_to_review_true_for_skills_only(ws_project):
    _commit_skill(".claude/skills/a/b.md")
    assert gate.nothing_to_review(Path.cwd()) is True


def test_x12_nothing_to_review_false_for_ordinary_commit(ws_project):
    _commit("own")
    assert gate.nothing_to_review(Path.cwd()) is False


_COMPLETE = {
    "code_changed": True, "added": ["t.py::a"], "red": ["t.py::a"], "green": ["t.py::a"],
    "failed": [], "breaks": [], "tests_touched": [], "uncovered": [],
}


def _tests_review(folder, sha, code):
    (folder / "review-tests-1.md").write_text(
        f"<!-- pass: tests | model: m | base: commit {sha} | exit: {code} | t -->\nbody\n"
    )


def test_us2_reviewed_true_for_tests_review_exit_zero(tmp_path):
    _tests_review(tmp_path, SHA, 0)
    assert gate.reviewed(tmp_path, SHA) is True


def test_us2_reviewed_false_for_tests_review_exit_one(tmp_path):
    _tests_review(tmp_path, SHA, 1)
    assert gate.reviewed(tmp_path, SHA) is False


def test_us2_reviewed_true_for_complete_evidence_record_full_sha(tmp_path):
    (tmp_path / f"evidence-{SHA}.json").write_text(json.dumps(_COMPLETE))
    assert gate.reviewed(tmp_path, SHA) is True


def test_us2_reviewed_true_for_complete_evidence_record_short_sha(tmp_path):
    (tmp_path / "evidence-abc1234.json").write_text(json.dumps(_COMPLETE))
    assert gate.reviewed(tmp_path, "abc1234") is True


def test_us2_reviewed_false_for_incomplete_evidence_record(tmp_path):
    (tmp_path / f"evidence-{SHA}.json").write_text(json.dumps({**_COMPLETE, "green": []}))
    assert gate.reviewed(tmp_path, SHA) is False


def test_us2_reviewed_false_for_invalid_json_evidence(tmp_path):
    (tmp_path / f"evidence-{SHA}.json").write_text("{not json")
    assert gate.reviewed(tmp_path, SHA) is False


def test_us2_reviewed_true_for_commit_review_still(tmp_path):
    (tmp_path / "review-commit-2.md").write_text(_header("commit", SHA))
    assert gate.reviewed(tmp_path, SHA) is True


def test_us2_reviewed_false_with_no_files(tmp_path):
    assert gate.reviewed(tmp_path, SHA) is False


def test_us2_gate_message_names_all_three_ways_to_unblock(ws_project, capsys):
    _commit("own")
    assert gate.main(ws_project) == 1
    err = capsys.readouterr().err.lower()
    assert "commit review" in err
    assert "tests review" in err
    assert "evidence" in err
