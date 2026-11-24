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


def _stories_and_body(unit_md: str) -> tuple[str, str]:
    lines = unit_md.splitlines()
    head = _HEAD.sub("", lines[0])
    found = re.fullmatch(r"(.*) \(([^()]*)\)\s*", head)
    title, stories = (found.group(1), found.group(2)) if found else (head.strip(), "")
    fix = lines[1][5:] if len(lines) > 1 and lines[1].startswith("Fix: ") else ""
    return stories, f"Fix {fix}: {title}" if fix else title


def commit_message(unit_md: str) -> str:
    """Return the commit message for a unit's text: `<stories>: <title>`, or the title alone.

    Reads the first `### n. <title> (<stories>)` line; stories are the last parentheses.
    When the next line is `Fix: <fix>`, returns `<stories>: Fix <fix>: <title>`.
    """
    stories, body = _stories_and_body(unit_md)
    return f"{stories}: {body}" if stories else body


def test_commit_message(unit_md: str) -> str:
    """Return the message for a unit's test commit: `test(<stories>): <body>`, or `test: <body>` without stories.

    The body is the one `commit_message` builds, so a fix unit gives `Fix <fix>: <title>`.
    """
    stories, body = _stories_and_body(unit_md)
    return f"test({stories}): {body}" if stories else f"test: {body}"


def _field(unit_md: str, name: str) -> str | None:
    found = re.search(rf"^{name}:[ \t]*(.*?)[ \t]*$", unit_md, re.MULTILINE)
    return found.group(1) if found else None


def unit_lane(unit_md: str) -> str:
    """Return "fast" when the unit has a `Lane: fast` line, else "full" (also for unknown values)."""
    return "fast" if _field(unit_md, "Lane") == "fast" else "full"


def declared_breaks(unit_md: str) -> list[str]:
    """Return the comma-separated, stripped ids of the unit's `Breaks:` line, or [] without one."""
    return [i.strip() for i in (_field(unit_md, "Breaks") or "").split(",") if i.strip()]
