import importlib.util
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
_path = _root / "scripts" / "hooks" / "slop_checks.py"
_spec = importlib.util.spec_from_file_location("slop_checks", _path)
slop = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(slop)


def lines(findings):
    return [line for line, _ in findings]


# justification_comments


def test_x2_workaround_comment_flagged_with_line_and_message():
    out = slop.justification_comments("x = 1\n# workaround for a bug\n")
    assert lines(out) == [2]
    assert out[0][1] == ("SLOP001 comment justifies a workaround: fix the cause or delete the comment")


def test_x2_workaround_word_inside_string_not_flagged():
    assert slop.justification_comments('s = "# workaround"\nt = """\nhack\n"""\n') == []


def test_x2_each_justification_phrase_flagged_case_insensitive():
    for phrase in ["workaround", "for now", "hack", "temporary", "temporarily", "in case", "quick fix"]:
        src = f"x = 1  # {phrase.upper()} here\n"
        assert lines(slop.justification_comments(src)) == [1], phrase


def test_x2_plain_comment_not_flagged():
    assert slop.justification_comments("# explains the invariant\nx = 1\n") == []


# hidden_state


def test_x2_module_constant_dict_read_in_function_not_flagged():
    src = "EDGES = {'a': ['b']}\n\ndef f(n):\n    return EDGES[n] + list(EDGES.keys())\n"
    assert slop.hidden_state(src) == []


def test_x2_function_appending_to_module_list_flagged():
    src = "ITEMS = []\n\ndef f(x):\n    ITEMS.append(x)\n"
    out = slop.hidden_state(src)
    assert lines(out) == [4]
    assert out[0][1] == ("SLOP002 function mutates module state ITEMS: pass it in and return the result")


def test_x2_parameter_shadowing_module_name_not_flagged():
    src = "ITEMS = []\n\ndef f(ITEMS):\n    ITEMS.append(1)\n    ITEMS['a'] = 2\n"
    assert slop.hidden_state(src) == []


def test_x2_local_assignment_shadowing_module_name_not_flagged():
    src = "ITEMS = []\n\ndef f():\n    ITEMS = []\n    ITEMS.append(1)\n"
    assert slop.hidden_state(src) == []


def test_x2_global_and_nonlocal_flagged_with_line():
    src = (
        "N = 0\n\ndef f():\n    global N\n    N = 1\n\n"
        "def g():\n    v = 0\n    def h():\n        nonlocal v\n        v = 1\n"
    )
    out = slop.hidden_state(src)
    assert 4 in lines(out)
    assert 10 in lines(out)


def test_x2_module_level_code_itself_not_flagged():
    src = "ITEMS = []\nITEMS.append(1)\nD = {}\nD['a'] = 1\nD.update(b=2)\n"
    assert slop.hidden_state(src) == []


def test_x2_subscript_attribute_augmented_and_del_flagged():
    src = (
        "D = {}\nO = object()\nN = 0\n\n"
        "def a():\n    D['k'] = 1\n"
        "def b():\n    O.x = 1\n"
        "def c():\n    N += 1\n"
        "def d():\n    del D['k']\n"
        "def e():\n    D['k'] += 1\n"
        "def f():\n    del O.x\n"
    )
    assert lines(slop.hidden_state(src)) == [6, 8, 10, 12, 14, 16]


def test_x2_each_mutating_method_flagged():
    methods = [
        "append",
        "extend",
        "insert",
        "update",
        "setdefault",
        "pop",
        "popitem",
        "clear",
        "add",
        "remove",
        "discard",
    ]
    for m in methods:
        src = f"S = set()\n\ndef f():\n    S.{m}(1)\n"
        out = slop.hidden_state(src)
        assert lines(out) == [4], m
        assert "SLOP002" in out[0][1] and "S" in out[0][1]


def test_x2_non_mutating_method_on_module_name_not_flagged():
    assert slop.hidden_state("S = {1}\n\ndef f():\n    return S.copy(), S.get(1)\n") == []


# banned_imports


def test_x2_from_subprocess_import_flagged():
    out = slop.banned_imports("x = 1\nfrom subprocess import run\n", {"subprocess"})
    assert lines(out) == [2]
    assert out[0][1] == ("SLOP003 subprocess imported in a pure module: move the I/O to the caller")


def test_x2_import_banned_module_and_submodule_flagged():
    out = slop.banned_imports("import subprocess\nimport os.path\n", {"subprocess", "os"})
    assert lines(out) == [1, 2]


def test_x2_unbanned_import_not_flagged():
    assert slop.banned_imports("import json\nfrom pathlib import Path\n", {"subprocess"}) == []


# main


def test_x2_main_flags_subprocess_under_scripts_workflow(tmp_path, capsys):
    f = tmp_path / "scripts" / "workflow" / "m.py"
    f.parent.mkdir(parents=True)
    f.write_text("import subprocess\n")
    assert slop.main([str(f)]) == 1
    out = capsys.readouterr().out
    assert f"{f}:1: SLOP003 subprocess imported" in out


def test_x2_main_allows_subprocess_under_scripts_hooks(tmp_path, capsys):
    f = tmp_path / "scripts" / "hooks" / "m.py"
    f.parent.mkdir(parents=True)
    f.write_text("import subprocess\n")
    assert slop.main([str(f)]) == 0
    assert capsys.readouterr().out == ""


def test_x2_main_reports_comment_and_state_findings(tmp_path, capsys):
    f = tmp_path / "m.py"
    f.write_text("L = []\n# hack\ndef f():\n    L.append(1)\n")
    assert slop.main([str(f)]) == 1
    out = capsys.readouterr().out
    assert f"{f}:2: SLOP001" in out
    assert f"{f}:4: SLOP002" in out


def test_x2_main_clean_file_exit_zero(tmp_path):
    f = tmp_path / "m.py"
    f.write_text("def f(x):\n    return x + 1\n")
    assert slop.main([str(f)]) == 0


def test_x2_current_scripts_tree_gives_exit_zero(capsys):
    files = sorted(str(p) for p in (_root / "scripts").rglob("*.py"))
    assert files
    assert slop.main(files) == 0, capsys.readouterr().out


def test_x2_justification_words_match_whole_words_only():
    source = "x = 1  # the hacker showcase\ny = 2  # a shack\n"
    assert slop.justification_comments(source) == []


def test_x2_write_inside_tuple_target_flagged():
    source = "STATE = {}\n\n\ndef f():\n    a, STATE['k'] = 1, 2\n    return a\n"
    assert lines(slop.hidden_state(source)) == [5]
