import importlib.util
import subprocess
from pathlib import Path

_path = Path(__file__).resolve().parents[1] / "scripts" / "new_project.py"
_spec = importlib.util.spec_from_file_location("new_project", _path)
np = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(np)


def test_files_fill_in_the_name_and_include_ci_and_gitignore():
    files = np.project_files("demo", "A demo project.")
    assert files["CLAUDE.md"].startswith("# demo") and "A demo project." in files["CLAUDE.md"]
    assert ".gitignore" in files and "gitignore" not in files
    assert {".github/workflows/branch-order.yml", ".github/workflows/tests.yml", "evals/cases/.gitkeep"} <= set(files)


def test_repo_starts_on_dev_with_main_and_uat(tmp_path):
    np.write_files(tmp_path, np.project_files("demo", "A demo project."))
    np.init_repo(tmp_path)
    branches = subprocess.run(["git", "-C", str(tmp_path), "branch"], capture_output=True, text=True, check=True).stdout
    assert "* dev" in branches and "main" in branches and "uat" in branches


def test_us27_scaffold_commit_passes_workspace_hooks_with_valid_subject(tmp_path, monkeypatch):
    hooks = Path(__file__).resolve().parents[1] / ".githooks"
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "core.hooksPath")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", str(hooks))
    np.write_files(tmp_path, np.project_files("demo", "A demo project."))
    np.init_repo(tmp_path)
    log = subprocess.run(
        ["git", "-C", str(tmp_path), "log", "main", "--format=%s"], capture_output=True, text=True, check=True
    ).stdout.splitlines()
    assert log == ["X0: Start from the workspace project template"]


def test_us27_write_files_makes_shebang_files_executable(tmp_path):
    np.write_files(tmp_path, {"a.py": "#!/usr/bin/env python3\n", "b.txt": "x\n"})
    assert (tmp_path / "a.py").stat().st_mode & 0o100
    assert not (tmp_path / "b.txt").stat().st_mode & 0o100
