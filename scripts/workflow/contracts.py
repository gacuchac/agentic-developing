"""Contract guard: find changed public signatures an approved architecture does not cover."""

from __future__ import annotations

import re

_DEF = re.compile(r"^-\s*def ([A-Za-z]\w*)\(")


def changed_signatures(diff: str) -> set[str]:
    """Return names of public functions whose `def` line is removed or changed in `diff`.

    Skips files with a `tests` path component; tracks files by `--- a/` headers.
    """
    names: set[str] = set()
    skip = False
    for line in diff.splitlines():
        if line.startswith("--- a/"):
            skip = "tests" in line[6:].split("/")[:-1]
        elif not skip and (m := _DEF.match(line)):
            names.add(m.group(1))
    return names


def uncovered(names: set[str], architecture: str) -> set[str]:
    """Return `names` unless `architecture` has a "Status: approved" line, else those it never mentions."""
    lines = architecture.lower().splitlines()
    if not any("status:" in x and "approved" in x for x in lines):
        return set(names)
    return {n for n in names if not re.search(rf"\b{n}\b", architecture)}
