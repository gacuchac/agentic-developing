import importlib.util
import subprocess
import sys
from pathlib import Path

_path = Path(__file__).resolve().parents[1] / "scripts" / "hooks" / "commit_cap.py"
_spec = importlib.util.spec_from_file_location("commit_cap", _path)
cap = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cap)


def test_edited_line_counts_once():
    assert cap.file_counts("1\t1\ta.py\n") == {"a.py": 1}


def test_larger_of_added_and_deleted_per_file():
    assert cap.count_changed_lines("5\t2\ta.py\n0\t7\tb.py\n") == 12


def test_rename_counts_zero_and_binary_counts_one():
    assert cap.count_changed_lines("0\t0\told.py => new.py\n-\t-\tlogo.png\n") == 1


def test_deleting_a_whole_file_counts_zero():
    counts = cap.without_deleted_files({"old.py": 140, "kept.py": 3}, "D\told.py\nM\tkept.py\n")
    assert counts == {"old.py": 0, "kept.py": 3}


def test_empty_numstat_counts_zero():
    assert cap.count_changed_lines("") == 0


def _stage_lines(repo: Path, n: int) -> None:
    """Make repo a git repo with n new lines staged."""
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / "f.py").write_text("".join(f"{i}\n" for i in range(n)))
    subprocess.run(["git", "-C", str(repo), "add", "f.py"], check=True)


def _run_cap(repo: Path) -> int:
    return subprocess.run([sys.executable, str(_path)], cwd=repo, capture_output=True, check=False).returncode


def _with_first_commit(repo: Path) -> Path:
    """Give repo a first commit, so the cap applies to what is staged next."""
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@t",
            "commit",
            "-q",
            "--allow-empty",
            "-m",
            "start",
        ],
        check=True,
    )
    return repo


def test_thirty_lines_pass_and_thirty_one_block(tmp_path):
    _stage_lines(_with_first_commit(tmp_path / "ok"), 30)
    _stage_lines(_with_first_commit(tmp_path / "big"), 31)
    assert _run_cap(tmp_path / "ok") == 0
    assert _run_cap(tmp_path / "big") == 1


def test_first_commit_is_exempt(tmp_path):
    _stage_lines(tmp_path, 200)
    assert _run_cap(tmp_path) == 0


def test_finishing_a_merge_is_exempt(tmp_path):
    _stage_lines(_with_first_commit(tmp_path), 31)
    (tmp_path / ".git" / "MERGE_HEAD").write_text("0" * 40 + "\n")
    assert _run_cap(tmp_path) == 0


def test_us1_test_files_count_zero():
    counts = cap.without_test_files({"tests/test_a.py": 40, "a/tests/b.py": 5, "tests.py": 3, "src/a.py": 2})
    assert counts == {"tests/test_a.py": 0, "a/tests/b.py": 0, "tests.py": 3, "src/a.py": 2}


def _stage_lines_at(repo: Path, rel: str, n: int) -> None:
    """Stage n new lines in repo/rel."""
    target = repo / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("".join(f"{i}\n" for i in range(n)))
    subprocess.run(["git", "-C", str(repo), "add", rel], check=True)


def test_us1_forty_lines_in_tests_dir_pass(tmp_path):
    _stage_lines_at(_with_first_commit(tmp_path), "tests/t.py", 40)
    assert _run_cap(tmp_path) == 0


def test_us1_thirty_one_lines_in_evals_cases_still_block(tmp_path):
    _stage_lines_at(_with_first_commit(tmp_path), "evals/cases/c.yaml", 31)
    assert _run_cap(tmp_path) == 1


def test_x1_markdown_counts_zero_at_any_depth_and_any_case():
    counts = cap.without_doc_files({"README.md": 50, "docs/a/b/c.md": 9, "NOTES.MD": 4, "x.Md": 2})
    assert counts == {"README.md": 0, "docs/a/b/c.md": 0, "NOTES.MD": 0, "x.Md": 0}


def test_x1_txt_rst_and_license_count_zero():
    counts = cap.without_doc_files({"a.txt": 5, "docs/b.rst": 6, "C.TXT": 1, "LICENSE": 40, "sub/LICENSE": 7})
    assert set(counts.values()) == {0}


def test_x1_code_and_config_files_keep_their_counts():
    original = {"a.py": 1, "pyproject.toml": 2, "c.json": 3, "run.sh": 4, ".githooks/pre-commit": 5}
    assert cap.without_doc_files(original) == original


def test_x1_input_is_not_mutated():
    original = {"a.md": 10, "b.py": 3}
    cap.without_doc_files(original)
    assert original == {"a.md": 10, "b.py": 3}


def _stage_two(repo: Path, doc_lines: int, py_lines: int) -> None:
    _stage_lines_at(repo, "docs/guide.md", doc_lines)
    _stage_lines_at(repo, "src/a.py", py_lines)


def test_x1_two_hundred_markdown_lines_plus_ten_python_pass(tmp_path):
    _stage_two(_with_first_commit(tmp_path), 200, 10)
    assert _run_cap(tmp_path) == 0


def test_x1_thirty_one_python_lines_still_block_beside_markdown(tmp_path):
    _stage_two(_with_first_commit(tmp_path), 200, 31)
    assert _run_cap(tmp_path) == 1


def test_x9_skill_files_count_zero_including_their_scripts():
    counts = {".claude/skills/statechart/scripts/run.ts": 400, ".claude/skills/x/SKILL.md": 9, "scripts/a.py": 5}
    assert cap.without_skill_files(counts) == {
        ".claude/skills/statechart/scripts/run.ts": 0,
        ".claude/skills/x/SKILL.md": 0,
        "scripts/a.py": 5,
    }


def test_x9_only_the_workspace_skills_folder_is_exempt():
    counts = {"src/.claude/skills/a.ts": 4, "claude/skills/a.ts": 3, ".claude/settings.json": 2}
    assert cap.without_skill_files(counts) == counts


def test_x9_vendored_skill_scripts_pass_main(tmp_path, monkeypatch):
    repo = _with_first_commit(tmp_path)
    _stage_lines_at(repo, ".claude/skills/statechart/scripts/run.ts", 500)
    monkeypatch.chdir(repo)
    assert cap.main() == 0
