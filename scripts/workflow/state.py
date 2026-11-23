"""Create, load and save a task's workflow state (state.json in its run folder)."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


def new_state(task: str, branch: str, launch: str, plan: str = "plan.md", mode: str = "sequential") -> dict:
    """Return the initial state: build stage, unit 1, node write_unit, round 1, no history."""
    return {"task": task, "branch": branch, "launch": launch, "mode": mode, "plan": plan, "stage": "build", "unit": 1,
            "fix": 0, "node": "write_unit", "round": 1, "pending": {"kind": "auto"}, "head": None, "history": []}


def unit_label(state: dict) -> str:
    """Return the unit as "7", or "7-fix2" on fix round 2."""
    return f"{state['unit']}-fix{state['fix']}" if state["fix"] > 0 else str(state["unit"])


def load(run: Path) -> dict:
    """Read the state from run/state.json."""
    return json.loads((Path(run) / "state.json").read_text())


def save(run: Path, state: dict) -> None:
    """Write the state as indented JSON to run/state.json, atomically via a temp file."""
    with tempfile.NamedTemporaryFile("w", dir=run, delete=False) as f:
        json.dump(state, f, indent=2)
    os.replace(f.name, Path(run) / "state.json")
