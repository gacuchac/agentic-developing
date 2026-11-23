"""Result schemas for the qa and implementer agents, and a validator for them."""

from __future__ import annotations

import schema

SCHEMAS: dict = {
    "qa": {"tests_added": [str], "red_run": {"failed": [str], "reason_expected": bool}},
    "implementer": {"files": {str: int}, "tests_run": {"passed": int, "failed": [str]}},
}


def validate_result(agent: str, data: object) -> list[str]:
    """Check an agent's result against SCHEMAS[agent]; return one error per bad field.

    Each error names its JSON path ("red_run.reason_expected", "files.a.py",
    "tests_added[1]"). Extra keys are allowed. Returns [] when valid, and an error
    naming the agent when it is unknown. Never raises and never mutates data.
    """
    if agent not in SCHEMAS:
        return [f"unknown agent: {agent}"]
    return schema.check(SCHEMAS[agent], data)
