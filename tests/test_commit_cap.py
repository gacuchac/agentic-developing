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
    (repo / "f.txt").write_text("".join(f"{i}\n" for i in range(n)))
    subprocess.run(["git", "-C", str(repo), "add", "f.txt"], check=True)


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
