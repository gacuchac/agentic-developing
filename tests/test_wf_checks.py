"""Tests for effects.checks: run pytest and read failing ids."""
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
