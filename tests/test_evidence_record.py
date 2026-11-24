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
