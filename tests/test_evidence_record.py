import importlib.util
from pathlib import Path

_path = Path(__file__).resolve().parents[1] / "scripts" / "hooks" / "evidence_record.py"
_spec = importlib.util.spec_from_file_location("evidence_record", _path)
er = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(er)


def _diff(path: str, *lines: str) -> str:
    body = "".join(f"+{line}\n" for line in lines)
    return f"diff --git a/{path} b/{path}\n--- /dev/null\n+++ b/{path}\n@@ -0,0 +1,{len(lines)} @@\n{body}"


def _record(**over):
    rec = {
        "code_changed": True,
        "added": ["t.py::a"],
        "red": ["t.py::a"],
        "green": ["t.py::a"],
        "failed": [],
        "breaks": [],
        "tests_touched": [],
        "uncovered": [],
    }
    rec.update(over)
    return rec


def test_us9_added_tests_lists_sync_and_async_tests():
    diff = _diff("tests/test_a.py", "def test_a():", "    pass", "async def test_b():", "    pass")
    assert er.added_tests(diff) == ["tests/test_a.py::test_a", "tests/test_a.py::test_b"]


def test_us9_added_tests_ignores_non_test_function():
    assert er.added_tests(_diff("tests/test_a.py", "def helper():", "    pass")) == []


def test_us9_added_tests_ignores_test_outside_tests_directory():
    assert er.added_tests(_diff("src/test_x.py", "def test_x():", "    pass")) == []


def test_us9_added_tests_tracks_each_file_by_header():
    diff = _diff("tests/test_a.py", "def test_a():") + _diff("tests/test_b.py", "def test_b():")
    assert er.added_tests(diff) == ["tests/test_a.py::test_a", "tests/test_b.py::test_b"]


def test_us9_complete_true_for_full_record():
    assert er.complete(_record()) is True


def test_us9_complete_false_when_added_not_red():
    assert er.complete(_record(red=[])) is False


def test_us9_complete_false_when_added_not_green():
    assert er.complete(_record(green=[])) is False


def test_us9_complete_false_when_failure_not_in_breaks():
    assert er.complete(_record(failed=["t.py::z"])) is False


def test_us9_complete_true_when_failure_is_in_breaks():
    assert er.complete(_record(failed=["t.py::z"], breaks=["t.py::z"])) is True


def test_us9_complete_false_when_tests_touched():
    assert er.complete(_record(tests_touched=["tests/test_a.py"])) is False


def test_us9_complete_false_when_uncovered():
    assert er.complete(_record(uncovered=["f(x)"])) is False


def test_us9_complete_false_when_code_changed_with_nothing_added():
    assert er.complete(_record(added=[], red=[], green=[])) is False


def test_us9_complete_false_when_field_missing():
    rec = _record()
    del rec["uncovered"]
    assert er.complete(rec) is False


def test_us9_complete_true_when_no_code_changed_and_nothing_added():
    assert er.complete(_record(code_changed=False, added=[], red=[], green=[])) is True


import json
import subprocess
import sys

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "hooks" / "evidence_record.py"
_SRC = Path(__file__).resolve().parents[1]
_TEST_B = (
    "import sys\nfrom pathlib import Path\n"
    "sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))\n"
    "from a import f\n\n\ndef test_b():\n    assert f() == 2\n"
)


def _git(repo: Path, *args: str) -> str:
    cmd = ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args]
    return subprocess.run(cmd, cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


def _commit(repo: Path, msg: str, files: dict[str, str]) -> str:
    for name, text in files.items():
        (repo / name).parent.mkdir(parents=True, exist_ok=True)
        (repo / name).write_text(text)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", msg)
    return _git(repo, "rev-parse", "HEAD")


def _repo(tmp_path: Path, *, with_tests: bool = True):
    repo, run = tmp_path / "repo", tmp_path / "run"
    repo.mkdir()
    run.mkdir()
    _git(repo, "init", "-q")
    (run / "architecture.md").write_text("Status: approved\n")
    (run / "unit.md").write_text("# unit\n")
    test_a = (
        "import sys\nfrom pathlib import Path\n"
        "sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))\n"
        "from a import f\n\n\ndef test_a():\n    assert f() >= 1\n"
    )
    _commit(repo, "US-1: base", {"src/a.py": "def f():\n    return 1\n", "tests/test_a.py": test_a})
    tests_sha = _commit(repo, "test(US-1): new test", {"tests/test_b.py": _TEST_B}) if with_tests else None
    return repo, run, tests_sha


def _measure(repo, run, sha):
    return er.measure(repo, run, sha, Path(sys.executable))


def test_us9_measure_complete_record_for_red_then_green_fix(tmp_path):
    repo, run, tests_sha = _repo(tmp_path)
    fix = _commit(repo, "US-1: fix", {"src/a.py": "def f():\n    return 2\n"})
    rec = _measure(repo, run, fix)
    assert rec["tests_commit"] == tests_sha
    assert rec["added"] == ["tests/test_b.py::test_b"]
    assert rec["red"] == rec["added"]
    assert rec["green"] == rec["added"]
    assert rec["failed"] == []
    assert rec["tests_touched"] == []
    assert rec["uncovered"] == []
    assert rec["code_changed"] is True
    assert er.complete(rec) is True


def test_us9_measure_fix_leaving_test_failing_is_incomplete(tmp_path):
    repo, run, _ = _repo(tmp_path)
    fix = _commit(repo, "US-1: fix", {"src/a.py": "def f():\n    return 3\n"})
    rec = _measure(repo, run, fix)
    assert rec["green"] == []
    assert er.complete(rec) is False


def test_us9_measure_reports_tests_edited_after_test_commit(tmp_path):
    repo, run, _ = _repo(tmp_path)
    fix = _commit(
        repo, "US-1: fix", {"src/a.py": "def f():\n    return 2\n", "tests/test_b.py": _TEST_B + "\n# edit\n"}
    )
    rec = _measure(repo, run, fix)
    assert "tests/test_b.py" in rec["tests_touched"]
    assert er.complete(rec) is False


def test_us9_measure_code_without_test_commit_is_incomplete(tmp_path):
    repo, run, _ = _repo(tmp_path, with_tests=False)
    fix = _commit(repo, "US-1: fix", {"src/a.py": "def f():\n    return 2\n"})
    rec = _measure(repo, run, fix)
    assert rec["tests_commit"] is None
    assert rec["added"] == []
    assert rec["code_changed"] is True
    assert er.complete(rec) is False


def test_us9_measure_reads_breaks_line_of_unit_md(tmp_path):
    repo, run, _ = _repo(tmp_path)
    (run / "unit.md").write_text("# unit\nBreaks: tests/test_a.py::test_a, tests/x.py\n")
    fix = _commit(repo, "US-1: fix", {"src/a.py": "def f():\n    return 2\n"})
    assert _measure(repo, run, fix)["breaks"] == ["tests/test_a.py::test_a", "tests/x.py"]


def test_us9_measure_describes_the_commit_not_the_working_tree(tmp_path):
    repo, run, _ = _repo(tmp_path)
    fix = _commit(repo, "US-1: fix", {"src/a.py": "def f():\n    return 3\n"})
    (repo / "src" / "a.py").write_text("def f():\n    return 2\n")
    rec = _measure(repo, run, fix)
    assert rec["green"] == []
    assert er.complete(rec) is False


def _write(repo: Path, run: Path, sha: str):
    cmd = [sys.executable, str(_SCRIPT), "write", "--run", str(run), "--sha", sha, "--python", sys.executable]
    return subprocess.run(cmd, cwd=repo, capture_output=True, text=True)


def test_us9_cli_write_saves_record_and_exits_zero_when_complete(tmp_path):
    repo, run, _ = _repo(tmp_path)
    fix = _commit(repo, "US-1: fix", {"src/a.py": "def f():\n    return 2\n"})
    proc = _write(repo, run, fix)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    saved = json.loads((run / f"evidence-{fix}.json").read_text())
    assert saved["added"] == ["tests/test_b.py::test_b"]


def test_us9_cli_write_exits_one_and_names_failing_field(tmp_path):
    repo, run, _ = _repo(tmp_path)
    fix = _commit(repo, "US-1: fix", {"src/a.py": "def f():\n    return 3\n"})
    proc = _write(repo, run, fix)
    assert proc.returncode == 1
    assert "green" in proc.stdout + proc.stderr


def test_us9_is_failed_exact_match():
    assert er.is_failed("tests/a.py::test_x", ["tests/a.py::test_x"]) is True


def test_us9_is_failed_parametrized_case_counts():
    assert er.is_failed("tests/a.py::test_x", ["tests/a.py::test_x[1]"]) is True


def test_us9_is_failed_longer_name_does_not_count():
    assert er.is_failed("tests/a.py::test_x", ["tests/a.py::test_x_extra"]) is False


def test_us9_is_failed_empty_failed_list_is_false():
    assert er.is_failed("tests/a.py::test_x", []) is False


def test_us9_is_failed_file_level_id_counts_for_its_tests():
    assert er.is_failed("tests/a.py::test_x", ["tests/a.py"]) is True


def test_us9_measure_collection_error_at_test_commit_counts_as_red(tmp_path):
    repo, run, _ = _repo(tmp_path, with_tests=False)
    test_c = (
        "import sys\nfrom pathlib import Path\n"
        "sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))\n"
        "from newmod import g\n\n\ndef test_c():\n    assert g() == 5\n"
    )
    _commit(repo, "test(US-1): new test", {"tests/test_c.py": test_c})
    fix = _commit(repo, "US-1: add module", {"src/newmod.py": "def g():\n    return 5\n"})
    rec = _measure(repo, run, fix)
    assert rec["added"] == ["tests/test_c.py::test_c"]
    assert rec["red"] == rec["added"]
    assert er.complete(rec) is True
