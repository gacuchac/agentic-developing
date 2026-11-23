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
