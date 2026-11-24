import json
import shutil
import subprocess
import sys
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
_PREFIX = '"${CLAUDE_PROJECT_DIR}"/.venv/bin/python '


def _workspace(tmp_path: Path, hook: str, scripts: tuple[str, ...]) -> tuple[Path, Path]:
    ws = tmp_path / "ws"
    (ws / ".githooks").mkdir(parents=True)
    (ws / "scripts" / "hooks").mkdir(parents=True)
    (ws / ".venv" / "bin").mkdir(parents=True)
    shutil.copy(_root / ".githooks" / hook, ws / ".githooks" / hook)
    for name in scripts:
        target = ws / "scripts" / "hooks" / name
        source = _root / "scripts" / "hooks" / name
        if name == "commit_msg.py":
            shutil.copy(source, target)
        else:
            target.write_text("import sys\nsys.exit(0)\n")
    marker = tmp_path / "marker"
    venv_python = ws / ".venv" / "bin" / "python"
    venv_python.write_text(f"#!/bin/sh\necho used >> '{marker}'\nexit 0\n")
    venv_python.chmod(0o755)
    return ws, marker


def test_us31_commit_msg_runs_with_workspace_venv_python(tmp_path):
    ws, marker = _workspace(tmp_path, "commit-msg", ("commit_msg.py",))
    msg = tmp_path / "msg"
    msg.write_text("not a valid subject at all\n")
    result = subprocess.run(
        [sys.executable, str(ws / ".githooks" / "commit-msg"), str(msg)], cwd=tmp_path
    )
    assert result.returncode == 0
    assert marker.exists()


def test_us31_pre_commit_runs_its_checks_with_workspace_venv_python(tmp_path):
    checks = ("lint_gate.py", "review_gate.py", "claim_gate.py")
    ws, marker = _workspace(tmp_path, "pre-commit", checks)
    result = subprocess.run(
        [sys.executable, str(ws / ".githooks" / "pre-commit")], cwd=tmp_path
    )
    assert result.returncode == 0
    assert marker.exists()
    assert len(marker.read_text().split()) == len(checks)


def test_us31_settings_hook_commands_use_workspace_venv_python():
    settings = json.loads((_root / ".claude" / "settings.json").read_text())
    commands = [
        hook["command"]
        for groups in settings["hooks"].values()
        for group in groups
        for hook in group["hooks"]
    ]
    assert commands
    for command in commands:
        assert command.startswith(_PREFIX), command
