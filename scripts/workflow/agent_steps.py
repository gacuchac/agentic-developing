"""Result schemas for the qa and implementer agents, and a validator for them."""

from __future__ import annotations

import json
from pathlib import Path

import schema

SCHEMAS: dict = {
    "qa": {"tests_added": [str], "red_run": {"failed": [str], "reason_expected": bool}},
    "qa_fix": {"tests_changed": [str]},
    "implementer": {"files": {str: int}, "tests_run": {"passed": int, "failed": [str]}, "tests_disputed": [str]},
    "subtract": {"removed": str, "files": {str: int}},
}

EXAMPLES: dict = {
    "qa": {"tests_added": ["tests/test_x.py"], "red_run": {"failed": ["test_x"], "reason_expected": True}},
    "qa_fix": {"tests_changed": ["tests/test_x.py"]},
    "implementer": {"files": {"src/x.py": 12}, "tests_run": {"passed": 3, "failed": []}, "tests_disputed": []},
    "subtract": {"removed": "unused helper", "files": {"src/x.py": 4}},
}

RESULT_KEYS: dict[str, str] = {"write": "qa", "fix": "qa_fix", "code": "implementer", "subtract": "subtract"}


def validate_result(agent: str, data: object) -> list[str]:
    """Check an agent's result against SCHEMAS[agent]; return one error per bad field.

    Each error names its JSON path ("red_run.reason_expected", "files.a.py",
    "tests_added[1]"). Extra keys are allowed. Returns [] when valid, and an error
    naming the agent when it is unknown. Never raises and never mutates data.
    """
    if agent not in SCHEMAS:
        return [f"unknown agent: {agent}"]
    return schema.check(SCHEMAS[agent], data)


def render_prompt(agent: str, step: str, step_id: str, run: Path, repo: Path, unit: str, template: str | None) -> str:
    """Return the prompt for one agent step; agent must be a key of SCHEMAS.

    With a template, return template.format_map of step_id, run, repo, unit and schema
    (the example result JSON) and nothing more; an unknown placeholder raises KeyError.
    Without one, return the default: first line "wf-step: <step_id>", then the agent,
    step, run folder, repo, unit text, a "do not commit" rule and a fenced
    workflow-result example block.
    """
    example = json.dumps(EXAMPLES[RESULT_KEYS[step]], indent=2)
    if template is not None:
        fields = {"step_id": step_id, "run": run, "repo": repo, "unit": unit, "schema": example}
        return template.format_map(fields)
    return (
        f"wf-step: {step_id}\nAgent: {agent}\nStep: {step}\nRun folder: {run}\nRepo: {repo}\n\n"
        f"{unit}\n\nDo not commit; leave changes uncommitted.\n"
        f"End with your result in this shape:\n```workflow-result\n{example}\n```\n"
    )
