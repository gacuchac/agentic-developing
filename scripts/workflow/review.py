"""Derive a review's verdict from its criterion lines, never from the VERDICT line."""

from __future__ import annotations

import re
from pathlib import Path

from scripts.workflow.evidence import quote_in


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


def dropped_fails(review: str, source: str) -> list[str]:
    """Return the FAIL ids, in review order, whose criterion text (its line and the lines
    up to the next criterion) has no backticked span found in source. An id with a
    quoted FAIL is kept."""
    blocks = re.split(r"\n(?=\s*(?:- )?\**[A-Z]\d+\**:)", review)
    quoted: dict[str, bool] = {}
    for block in blocks:
        for cid, word in parse_criteria(block).items():
            if word == "FAIL":
                spans = re.findall(r"`([^`]+)`", block)
                quoted[cid] = quoted.get(cid, False) or any(quote_in([source], s) for s in spans)
    return [cid for cid, ok in quoted.items() if not ok]


def derive_verdict(review: str, expected: list[str], source: str | None = None) -> tuple[str, list[str]]:
    """Return ("MALFORMED", []) if expected is empty or an id is missing, else
    ("CHANGES", fail ids in expected order) if any FAIL, else ("PASS", []).
    Given a source, FAILs from dropped_fails(review, source) do not count.
    The VERDICT line is never read."""
    found = parse_criteria(review)
    if not expected or any(i not in found for i in expected):
        return "MALFORMED", []
    dropped = dropped_fails(review, source) if source is not None else []
    fails = [i for i in expected if found[i] == "FAIL" and i not in dropped]
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
