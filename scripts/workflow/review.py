"""Derive a review's verdict from its criterion lines, never from the VERDICT line."""

from __future__ import annotations

import re


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
