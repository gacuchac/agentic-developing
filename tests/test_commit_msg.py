import importlib.util
from pathlib import Path

import pytest

_root = Path(__file__).resolve().parents[1]
_path = _root / "scripts" / "hooks" / "commit_msg.py"
_spec = importlib.util.spec_from_file_location("commit_msg", _path)
cm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cm)


@pytest.mark.parametrize(
    "subject",
    [
        "US-1: Add the thing",
        "US-12: Add the thing",
        "test(US-3): checks the thing",
        "X2: Run the slop checks",
        "X2 (6/7): Flag global and nonlocal",
        "US-9 (1/3): Split it",
        "test(US-3) (2/4): checks it",
        "US-9: Fix principles P1 on f1b0e8d: expand targets",
        "Merge branch 'x'",
        "Revert \"X2: something\"",
    ],
)
def test_x4_valid_subjects(subject):
    assert cm.valid_subject(subject) is True


@pytest.mark.parametrize(
    "subject",
    [
        "Update stuff",
        "",
        "US-1:",
        "US-1: ",
        "X2:",
        "X2 (6/7):",
        "test(US-3):",
        "US-: text",
        "X: text",
        "us-1: text",
        "US-1 text",
        "Fix: US-1: text",
    ],
)
def test_x4_invalid_subjects(subject):
    assert cm.valid_subject(subject) is False


def _msg(tmp_path: Path, text: str) -> str:
    path = tmp_path / "COMMIT_EDITMSG"
    path.write_text(text)
    return str(path)


def test_x4_main_valid_message_returns_zero(tmp_path, capsys):
    assert cm.main([_msg(tmp_path, "X2 (6/7): do it\n\nbody text\n")]) == 0
    assert capsys.readouterr().err == ""


def test_x4_main_only_first_line_is_checked(tmp_path):
    assert cm.main([_msg(tmp_path, "Update stuff\nUS-1: later line\n")]) == 1


def test_x4_main_invalid_message_prints_hint_and_returns_one(tmp_path, capsys):
    assert cm.main([_msg(tmp_path, "Update stuff\n")]) == 1
    err = capsys.readouterr().err
    assert "commit message must start with US-n:, test(US-n): or X<n>: (got: Update stuff)" in err


def test_x4_main_empty_text_after_colon_is_invalid(tmp_path):
    assert cm.main([_msg(tmp_path, "US-4:\n")]) == 1


@pytest.mark.parametrize("subject", ["US-9, US-10: x", "test(US-9, US-10): x"])
def test_us10_valid_story_lists(subject):
    assert cm.valid_subject(subject) is True
