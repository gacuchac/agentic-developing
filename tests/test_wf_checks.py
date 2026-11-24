"""Tests for effects.checks: run pytest and read failing ids."""
import subprocess
import sys
from pathlib import Path

from effects import checks

SUMMARY = """\
============================= test session starts ==============================
collected 2 items

=========================== short test summary info ============================
FAILED tests/t.py::test_a - assert 1 == 2
ERROR tests/u.py - SyntaxError: invalid syntax
========================= 1 failed, 1 error in 0.10s ==========================
"""


def test_us10_failed_ids_reads_failed_and_error_lines():
    assert checks.failed_ids(SUMMARY) == ["tests/t.py::test_a", "tests/u.py"]


def test_us10_failed_ids_empty_when_all_pass():
    assert checks.failed_ids("1 passed in 0.01s\n") == []


def test_us10_all_red_true_when_every_test_failed():
    assert checks.all_red(["a.py::t1", "a.py::t2"], ["a.py::t1", "a.py::t2"]) is True


def test_us10_all_red_file_error_covers_its_tests():
    assert checks.all_red(["tests/u.py::t1", "tests/u.py::t2"], ["tests/u.py"]) is True


def test_us10_all_red_false_for_empty_tests():
    assert checks.all_red([], ["a.py::t1"]) is False


def test_us10_all_red_false_when_one_test_not_failed():
    assert checks.all_red(["a.py::t1", "a.py::t2"], ["a.py::t1"]) is False


def _repo(tmp_path, with_fail):
    (tmp_path / "test_ok.py").write_text("def test_ok():\n    assert True\n")
    if with_fail:
        (tmp_path / "test_bad.py").write_text("def test_bad():\n    assert 1 == 2\n")
    return tmp_path


def test_us10_run_pytest_reports_code_and_failing_id(tmp_path):
    repo = _repo(tmp_path, True)
    res = checks.run_pytest(repo, ["test_ok.py", "test_bad.py"], python=Path(sys.executable))
    assert res == {"code": 1, "failed": ["test_bad.py::test_bad"]}


def test_us10_run_pytest_all_passing(tmp_path):
    repo = _repo(tmp_path, False)
    res = checks.run_pytest(repo, ["test_ok.py"], python=Path(sys.executable))
    assert res == {"code": 0, "failed": []}


def test_us10_run_pytest_uses_given_interpreter_outside_repo_venv(tmp_path):
    repo = _repo(tmp_path, False)
    assert not (repo / ".venv").exists()
    res = checks.run_pytest(repo, ["test_ok.py"], python=Path(sys.executable))
    assert res["code"] == 0


def test_us10_run_pytest_defaults_without_python_arg(tmp_path):
    repo = _repo(tmp_path, True)
    res = checks.run_pytest(repo, ["test_bad.py"])
    assert res["code"] == 1 and res["failed"] == ["test_bad.py::test_bad"]


def _git(repo, *args):
    import subprocess

    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=repo, check=True, capture_output=True,
    )


def _tmp_repo(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "src").mkdir()
    (tmp_path / "tests" / "t.py").write_text("a = 1\n")
    (tmp_path / "src" / "a.py").write_text("a = 1\n")
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "init")
    return tmp_path


def test_us10_tests_touched_lists_edited_and_untracked_test_files(tmp_path):
    repo = _tmp_repo(tmp_path)
    (repo / "tests" / "t.py").write_text("a = 2\n")
    (repo / "tests" / "u.py").write_text("b = 1\n")
    assert sorted(checks.tests_touched(repo)) == ["tests/t.py", "tests/u.py"]


def test_us10_tests_touched_ignores_non_test_changes(tmp_path):
    repo = _tmp_repo(tmp_path)
    (repo / "src" / "a.py").write_text("a = 2\n")
    assert checks.tests_touched(repo) == []


def test_us10_tests_touched_empty_on_clean_tree(tmp_path):
    repo = _tmp_repo(tmp_path)
    assert checks.tests_touched(repo) == []


def test_us18_fix_imports_sorts_an_unsorted_import_block(tmp_path):
    (tmp_path / "tests").mkdir()
    test_file = tmp_path / "tests" / "test_a.py"
    test_file.write_text("import sys\nimport os\n\n\ndef test_a():\n    assert os and sys\n")
    checks.fix_imports(tmp_path, ["tests/test_a.py"])
    assert test_file.read_text() == "import os\nimport sys\n\n\ndef test_a():\n    assert os and sys\n"


def test_us18_fix_imports_leaves_a_sorted_block_unchanged(tmp_path):
    (tmp_path / "tests").mkdir()
    test_file = tmp_path / "tests" / "test_a.py"
    text = "import os\nimport sys\n\n\ndef test_a():\n    assert os and sys\n"
    test_file.write_text(text)
    checks.fix_imports(tmp_path, ["tests/test_a.py"])
    assert test_file.read_text() == text


def test_us18_fix_imports_without_ruff_returns_and_leaves_file_unchanged(tmp_path, monkeypatch):
    (tmp_path / "tests").mkdir()
    test_file = tmp_path / "tests" / "test_a.py"
    text = "import sys\nimport os\n\n\ndef test_a():\n    assert os and sys\n"
    test_file.write_text(text)
    empty_bin = tmp_path / "empty_bin"
    empty_bin.mkdir()
    monkeypatch.setenv("PATH", str(empty_bin))
    checks.fix_imports(tmp_path, ["tests/test_a.py"])
    assert test_file.read_text() == text


def _size_repo(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("".join(f"line{i}\n" for i in range(10)))
    (tmp_path / "gone.py").write_text("".join(f"g{i}\n" for i in range(40)))
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "init")
    return tmp_path


def _lines(n):
    return "".join(f"x{i}\n" for i in range(n))


def test_us24_change_size_counts_untracked_and_edited_code_files(tmp_path):
    repo = _size_repo(tmp_path)
    (repo / "big.py").write_text(_lines(31))
    (repo / "src" / "a.py").write_text("".join(f"new{i}\n" for i in range(5)) + "".join(f"line{i}\n" for i in range(5, 10)))
    assert checks.change_size(repo) == {"big.py": 31, "src/a.py": 5}


def test_us24_change_size_leaves_out_tests_docs_skills_and_deleted_files(tmp_path):
    repo = _size_repo(tmp_path)
    (repo / "tests").mkdir()
    (repo / "tests" / "test_big.py").write_text(_lines(60))
    (repo / "notes.md").write_text(_lines(60))
    (repo / ".claude" / "skills" / "s").mkdir(parents=True)
    (repo / ".claude" / "skills" / "s" / "tool.py").write_text(_lines(60))
    (repo / "gone.py").unlink()
    (repo / "kept.py").write_text(_lines(3))
    assert checks.change_size(repo) == {"kept.py": 3}


def test_us24_change_size_stages_nothing(tmp_path):
    repo = _size_repo(tmp_path)
    (repo / "big.py").write_text(_lines(31))
    (repo / "src" / "a.py").write_text("changed\n")
    before = subprocess.run(["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True, check=True).stdout
    assert checks.change_size(repo) == {"big.py": 31, "src/a.py": 10}
    staged = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=repo, capture_output=True, text=True, check=True)
    assert staged.stdout == ""
    after = subprocess.run(["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True, check=True).stdout
    assert after == before
