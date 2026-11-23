"""Unit text from the plan, and fix-unit text."""

from __future__ import annotations

import re

_HEAD = re.compile(r"^### \d+[a-z]?\. ")


def plan_units(plan: str) -> list[str]:
    """Return each unit's text in order: from a `### n. ` heading to the next `### ` or `## ` line."""
    units: list[list[str]] = []
    inside = False
    for line in plan.splitlines():
        if _HEAD.match(line):
            units.append([line])
            inside = True
        elif line.startswith(("### ", "## ")):
            inside = False
        elif inside:
            units[-1].append(line)
    return ["\n".join(u) for u in units]


def fix_text(unit: str, fix: str, lines: list[str]) -> str:
    """Return unit's first line, `Fix: {fix}`, then lines, newline-joined with no trailing newline."""
    return "\n".join([unit.splitlines()[0], "Fix: " + fix, *lines])
