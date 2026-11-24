from __future__ import annotations

import re

_TEST_DEF = re.compile(r"^\+(?:async )?def (test_\w*)")
_FIELDS = ("code_changed", "added", "red", "green", "failed", "breaks", "tests_touched", "uncovered")


def added_tests(diff: str) -> list[str]:
    """Return `file::name` for each test function a diff adds under a `tests` directory."""
    found, path = [], ""
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            path = line[6:]
        elif (match := _TEST_DEF.match(line)) and "tests" in path.split("/")[:-1]:
            found.append(f"{path}::{match.group(1)}")
    return found


def complete(record: dict) -> bool:
    """Return True when added tests are red and green and nothing stray failed, changed or is uncovered."""
    added = set(record.get("added", ()))
    return (
        all(f in record for f in _FIELDS)
        and (bool(added) or not record["code_changed"])
        and added <= set(record["red"]) & set(record["green"])
        and set(record["failed"]) <= set(record["breaks"])
        and not (record["tests_touched"] or record["uncovered"])
    )
