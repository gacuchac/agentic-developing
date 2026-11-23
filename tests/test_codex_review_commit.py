import importlib.util
import subprocess
from pathlib import Path

_path = Path(__file__).resolve().parents[1] / "scripts" / "codex_review.py"
_spec = importlib.util.spec_from_file_location("codex_review", _path)
cr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cr)


def test_commit_pass_needs_commit_ask_and_plan():
    assert cr.missing_args("commit", {"commit": "abc"}) == ["--ask-file", "--plan-file"]


def test_answers_ask_needs_base_and_other_passes_need_nothing():
    assert cr.missing_args("answers-ask", {"ask_file": "a", "plan_file": "p"}) == ["--base"]
    assert cr.missing_args("principles", {}) == []


def _commit(repo: Path, name: str, text: str, message: str) -> str:
    """Write one file in repo, commit it with message, and return the new sha."""
    (repo / name).write_text(text)
    for cmd in (["add", name], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", message]):
        subprocess.run(["git", "-C", str(repo), *cmd], check=True)
    return subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()


def _repo_with_three_commits(repo: Path) -> list[str]:
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    return [_commit(repo, f"{n}.txt", f"{n} body\n", f"US-1: add {n}") for n in ("one", "two", "three")]


def test_commit_review_shows_only_that_commit_after_earlier_log(tmp_path, monkeypatch):
    base, second, third = _repo_with_three_commits(tmp_path)
    monkeypatch.chdir(tmp_path)
    shown = cr.commit_changes(third, base)
    assert "US-1: add two" in shown.split("### This commit")[0]
    assert "+three body" in shown and "+two body" not in shown


def test_answers_ask_sees_latest_branch_verdicts_and_no_diffs(tmp_path, monkeypatch):
    base, second, third = _repo_with_three_commits(tmp_path)
    monkeypatch.chdir(tmp_path)
    reviews = [(second, "VERDICT: CHANGES\nC2: FAIL — misses x"), (second, "VERDICT: PASS\nC1: PASS — ok"),
               ("f" * 40, "VERDICT: CHANGES\nC3: FAIL — stale"), (third, "VERDICT: CHANGES\nC2: FAIL — misses y")]
    for n, (sha, body) in enumerate(reviews, 1):
        (tmp_path / f"review-commit-{n}.md").write_text(f"<!-- pass: commit | base: commit {sha} | exit: 0 -->\n{body}\n")
    overview = cr.branch_overview(base, tmp_path)
    assert "US-1: add three" in overview and "three.txt" in overview and "+three body" not in overview
    assert "misses x" not in overview and "stale" not in overview
    assert "VERDICT: PASS" in overview and "C2: FAIL — misses y" in overview and "C1: PASS" not in overview


def test_pr_pass_needs_base_ask_and_plan_and_runs_on_sol(monkeypatch):
    assert cr.missing_args("pr", {"ask_file": "a"}) == ["--base", "--plan-file"]
    monkeypatch.setenv("CODEX_SOL_MODEL", "sol-model")
    assert cr.resolve_model("pr", None) == "sol-model"


def test_pr_changes_leave_out_target_commits_merged_in(tmp_path, monkeypatch):
    subprocess.run(["git", "init", "-q", "-b", "dev", str(tmp_path)], check=True)
    _commit(tmp_path, "base.txt", "base\n", "base")
    subprocess.run(["git", "-C", str(tmp_path), "switch", "-q", "-c", "feature/x"], check=True)
    _commit(tmp_path, "mine.txt", "mine\n", "US-1: mine")
    subprocess.run(["git", "-C", str(tmp_path), "switch", "-q", "dev"], check=True)
    _commit(tmp_path, "theirs.txt", "theirs\n", "other task")
    subprocess.run(["git", "-C", str(tmp_path), "switch", "-q", "feature/x"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "-c", "user.name=t", "-c", "user.email=t@t", "merge", "-q", "--no-edit", "dev"], check=True)
    (tmp_path / "scratch.txt").write_text("uncommitted\n")
    monkeypatch.chdir(tmp_path)
    changes = cr.pr_changes("dev")
    assert "+mine" in changes and "+theirs" not in changes and "uncommitted" not in changes
