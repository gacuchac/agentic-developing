from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_root / "scripts" / "workflow"))

import claims  # noqa: E402
from effects import claimfiles  # noqa: E402

_path = _root / "scripts" / "hooks" / "edit_guard.py"
_spec = importlib.util.spec_from_file_location("edit_guard", _path)
guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard)


def _claim(session: str, run: Path, checkout: Path) -> dict:
    return claims.make_claim(session, 1, "x", str(run), str(checkout), "feature/t", "now")


class World:
    def __init__(self, tmp_path: Path) -> None:
        self.ws = tmp_path / "ws"
        self.ws.mkdir()
        self.scratch = tmp_path / "scratch"
        self.mine = _claim("s1", self.ws / ".claude/runs/proj/t1", self.ws / ".worktrees/proj/t1")
        self.other = _claim("s2", self.ws / ".claude/runs/proj/t2", self.ws / ".worktrees/proj/t2")
        self.root = _claim("s3", self.ws / ".claude/runs/Developing/r", self.ws)


def _world(tmp_path: Path) -> World:
    return World(tmp_path)


def _allowed(w: World, path: str | Path, claim: dict | None, is_root: bool = False, others: list | None = None):
    return guard.path_allowed(str(path), claim, is_root, others if others is not None else [], str(w.ws))


def test_us14_no_claim_allows_any_path(tmp_path):
    w = _world(tmp_path)
    assert _allowed(w, w.ws / "scripts/x.py", None)[0] is True
    assert _allowed(w, w.other["checkout"] + "/a.py", None)[0] is True


def test_us14_allows_path_in_own_checkout(tmp_path):
    w = _world(tmp_path)
    assert _allowed(w, w.mine["checkout"] + "/src/a.py", w.mine, others=[w.other])[0] is True


def test_us14_allows_path_in_own_run_folder(tmp_path):
    w = _world(tmp_path)
    assert _allowed(w, w.mine["run"] + "/plan.md", w.mine, others=[w.other])[0] is True


def test_us14_project_task_denied_workspace_root_paths_naming_checkout(tmp_path):
    w = _world(tmp_path)
    for rel in (".claude/agents/qa.md", "scripts/wf.py", ".githooks/pre-commit", "CLAUDE.md", "docs/a.md"):
        allowed, reason = _allowed(w, w.ws / rel, w.mine)
        assert allowed is False, rel
        assert w.mine["checkout"] in reason, rel


def test_us14_root_task_allowed_workspace_root_paths(tmp_path):
    w = _world(tmp_path)
    for rel in (".claude/agents/qa.md", "scripts/wf.py", ".githooks/pre-commit", "CLAUDE.md", "docs/a.md"):
        assert _allowed(w, w.ws / rel, w.root, is_root=True)[0] is True, rel


def test_us14_denies_path_in_other_claims_checkout(tmp_path):
    w = _world(tmp_path)
    allowed, reason = _allowed(w, w.other["checkout"] + "/src/a.py", w.mine, others=[w.other])
    assert allowed is False and reason


def test_us14_denies_path_in_other_claims_run_folder(tmp_path):
    w = _world(tmp_path)
    assert _allowed(w, w.other["run"] + "/plan.md", w.mine, others=[w.other])[0] is False


def test_us14_root_task_denied_other_claims_checkout_inside_workspace(tmp_path):
    w = _world(tmp_path)
    path = w.other["checkout"] + "/src/a.py"
    assert _allowed(w, path, w.root, is_root=True, others=[w.other])[0] is False


def test_us14_allows_path_outside_workspace(tmp_path):
    w = _world(tmp_path)
    assert _allowed(w, w.scratch / "notes.txt", w.mine, others=[w.other])[0] is True


def _event(tool: str, path: str, session: str = "s1", key: str = "file_path") -> str:
    return json.dumps({"session_id": session, "tool_name": tool, "tool_input": {key: path}})


def _active(w: World, tmp_path: Path) -> Path:
    active = tmp_path / "active"
    claimfiles.create(active, "proj--t1.json", w.mine)
    claimfiles.create(active, "proj--t2.json", w.other)
    claimfiles.create(active, "Developing--r.json", w.root)
    return active


def test_us14_main_denies_edit_of_other_task_with_exit_2(tmp_path, capsys):
    w = _world(tmp_path)
    active = _active(w, tmp_path)
    code = guard.main(_event("Edit", w.other["checkout"] + "/a.py"), active, w.ws)
    assert code == 2
    assert capsys.readouterr().err.strip()


def test_us14_main_denies_write_and_notebook_edit(tmp_path):
    w = _world(tmp_path)
    active = _active(w, tmp_path)
    target = str(w.ws / "scripts/x.py")
    assert guard.main(_event("Write", target), active, w.ws) == 2
    assert guard.main(_event("NotebookEdit", target, key="notebook_path"), active, w.ws) == 2


def test_us14_main_allows_edit_in_own_checkout(tmp_path):
    w = _world(tmp_path)
    active = _active(w, tmp_path)
    assert guard.main(_event("Edit", w.mine["checkout"] + "/a.py"), active, w.ws) == 0


def test_us14_main_root_session_may_edit_scripts(tmp_path):
    w = _world(tmp_path)
    active = _active(w, tmp_path)
    assert guard.main(_event("Edit", str(w.ws / "scripts/x.py"), session="s3"), active, w.ws) == 0


def test_us14_main_project_session_may_not_edit_scripts(tmp_path):
    w = _world(tmp_path)
    active = _active(w, tmp_path)
    assert guard.main(_event("Edit", str(w.ws / "scripts/x.py")), active, w.ws) == 2


def test_us14_main_allows_scratch_path(tmp_path):
    w = _world(tmp_path)
    active = _active(w, tmp_path)
    assert guard.main(_event("Write", str(w.scratch / "n.txt")), active, w.ws) == 0


def test_us14_main_allows_other_tools(tmp_path):
    w = _world(tmp_path)
    active = _active(w, tmp_path)
    assert guard.main(_event("Read", w.other["checkout"] + "/a.py"), active, w.ws) == 0


def test_us14_main_allows_session_without_claim(tmp_path):
    w = _world(tmp_path)
    active = _active(w, tmp_path)
    assert guard.main(_event("Edit", w.other["checkout"] + "/a.py", session="nobody"), active, w.ws) == 0


def test_us14_main_allows_unreadable_input(tmp_path):
    w = _world(tmp_path)
    assert guard.main("not json", _active(w, tmp_path), w.ws) == 0
