"""Derive a review's verdict from its criterion lines, never from the VERDICT line."""

from __future__ import annotations

import re
from pathlib import Path


def rubric_ids(rubric: str) -> list[str]:
    """Return the ids of the rubric lines shaped `- C1. ...`, in file order."""
    return re.findall(r"^- ([A-Z]\d+)\. ", rubric, re.MULTILINE)


def parse_criteria(review: str) -> dict[str, str]:
    """Map each criterion id in a review to PASS, FAIL or N/A; a FAIL on any line wins."""
    found: dict[str, str] = {}
    for cid, word in re.findall(r"^\s*(?:- )?\**([A-Z]\d+)\**:\s*\**(PASS|FAIL|N/A)\b", review, re.MULTILINE):
        if found.get(cid) != "FAIL":
            found[cid] = word
    return found


def derive_verdict(review: str, expected: list[str]) -> tuple[str, list[str]]:
    """Return ("MALFORMED", []) if expected is empty or an id is missing, else
    ("CHANGES", fail ids in expected order) if any FAIL, else ("PASS", []).
    The VERDICT line is never read."""
    found = parse_criteria(review)
    if not expected or any(i not in found for i in expected):
        return "MALFORMED", []
    fails = [i for i in expected if found[i] == "FAIL"]
    return ("CHANGES", fails) if fails else ("PASS", [])


def review_args(pass_name: str, run: Path, plan: str, commit: str | None, base: str | None) -> list[str]:
    """Return codex_review's argv for a pass: [pass, --ask-file run/ask.md, --plan-file run/plan,
    --run-dir run], then --context-file run/unit.md for tests and impl, plus run/architecture.md
    for impl (a missing file is harmless), --commit when commit is given, --base when base is given.
    Paths are str."""
    args = [pass_name, "--ask-file", str(run / "ask.md"), "--plan-file", str(run / plan), "--run-dir", str(run)]
    context = {"tests": ["unit.md"], "impl": ["unit.md", "architecture.md"]}.get(pass_name, [])
    for name in context:
        args += ["--context-file", str(run / name)]
    if commit:
        args += ["--commit", commit]
    if base:
        args += ["--base", base]
    return args


def saved_path(stderr: str) -> Path | None:
    """Return the path after the last `saved: ` line of codex_review's stderr, or None if none."""
    found = re.findall(r"^saved: (.+)$", stderr, re.MULTILINE)
    return Path(found[-1].strip()) if found else None
