"""Tests for the wf command line (US-11), run as subprocesses."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
WF = ROOT / "scripts" / "workflow" / "wf.py"

PLAN = "# Plan\n\n### 1. First thing (US-1)\nLane: fast\nDo the first.\n\n### 2. Second thing (US-1)\nDo the second.\n"


def _g(repo, *args):
    subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True)


def wf(*args):
    return subprocess.run([sys.executable, str(WF), *map(str, args)], cwd=ROOT, capture_output=True, text=True)


@pytest.fixture
def env(tmp_path):
    repo = tmp_path / "Developing" / "proj"
    repo.mkdir(parents=True)
    _g(repo, "init", "-q", "-b", "main")
    _g(repo, "config", "user.email", "t@t")
    _g(repo, "config", "user.name", "t")
    (repo / "a.txt").write_text("a")
    _g(repo, "add", "-A")
    _g(repo, "commit", "-qm", "one")
    _g(repo, "branch", "dev")
    _g(repo, "checkout", "-q", "-b", "feature/x")
    run = tmp_path / "Developing" / ".claude" / "runs" / "proj" / "t1"
    run.mkdir(parents=True)
    (run / "plan.md").write_text(PLAN)
    (run / "ask.md").write_text("the ask\n")
    return run, repo


def _started(env):
    run, _ = env
    r = wf("start", run, "--plan", "plan.md")
    assert r.returncode == 0, r.stderr
    return run


def test_us11_start_creates_state_at_qa_write(env):
    run, repo = env
    r = wf("start", run, "--plan", "plan.md")
    assert r.returncode == 0, r.stderr
    state = json.loads((run / "state.json").read_text())
    assert state["node"] == "qa_write"
    assert state["branch"] == "feature/x"
    assert (
        state["launch"]
        == subprocess.run(["git", "rev-parse", "dev"], cwd=repo, capture_output=True, text=True).stdout.strip()
    )
    assert "qa_write" in r.stdout
    unit = (run / "unit.md").read_text()
    assert "First thing" in unit and "Second thing" not in unit


def test_us11_second_start_refused_state_unchanged(env):
    run = _started(env)
    before = (run / "state.json").read_bytes()
    r = wf("start", run, "--plan", "plan.md")
    assert r.returncode == 1
    assert r.stderr.strip()
    assert (run / "state.json").read_bytes() == before


def test_us11_start_with_no_units_refused(env):
    run, _ = env
    (run / "plan.md").write_text("# Plan\n\nnothing here\n")
    r = wf("start", run, "--plan", "plan.md")
    assert r.returncode == 1
    assert r.stderr.strip()
    assert not (run / "state.json").exists()


def test_us11_start_with_missing_plan_refused(env):
    run, _ = env
    r = wf("start", run, "--plan", "nope.md")
    assert r.returncode == 1
    assert r.stderr.strip()
    assert not (run / "state.json").exists()


def test_us11_status_prints_node(env):
    run = _started(env)
    r = wf("status", run)
    assert r.returncode == 0, r.stderr
    assert "qa_write" in r.stdout


def test_us11_options_prints_json_list_with_qa_launch(env):
    run = _started(env)
    r = wf("options", run)
    assert r.returncode == 0, r.stderr
    opts = json.loads(r.stdout)
    assert isinstance(opts, list) and opts
    assert "qa" in json.dumps(opts)


def test_us11_take_with_bad_evidence_refused_state_unchanged(env, tmp_path):
    run = _started(env)
    ev = tmp_path / "ev.json"
    ev.write_text("{}")
    before = (run / "state.json").read_bytes()
    r = wf("take", run, "escalate", "--evidence", ev)
    assert r.returncode == 1
    assert r.stderr.strip()
    assert (run / "state.json").read_bytes() == before


def test_us11_record_wrong_step_refused_state_unchanged(env, tmp_path):
    run = _started(env)
    res = tmp_path / "result.json"
    res.write_text(json.dumps({"tests_added": [], "red_run": {"failed": [], "reason_expected": True}}))
    before = (run / "state.json").read_bytes()
    r = wf("record", run, "wrong-step", res)
    assert r.returncode == 1
    assert (run / "state.json").read_bytes() == before


def test_us11_report_prints_headings(env):
    run = _started(env)
    (run / "decisions.tsv").write_text("")
    r = wf("report", run)
    assert r.returncode == 0, r.stderr
    assert "#" in r.stdout
