"""Contract guard: find changed public signatures an approved architecture does not cover."""

from __future__ import annotations

import re

_DEF = re.compile(r"^[ +-]\s*(?:async\s+)?def ([A-Za-z]\w*)\(")


def changed_signatures(diff: str) -> set[str]:
    """Return names of public functions whose signature changed in `diff`.

    A signature spans its `def` line to the first line ending in `:`. It counts when the `def`
    line is context or removed and any line of the span is added or removed; a new `def` does not.
    Skips files with a `tests` path component; tracks files by `--- a/` headers.
    """
    names: set[str] = set()
    skip = in_signature = False
    name = ""
    for line in diff.splitlines():
        if line.startswith("--- a/"):
            skip, in_signature = "tests" in line[6:].split("/")[:-1], False
            continue
        if skip or line.startswith(("+++", "@@")):
            in_signature = False
            continue
        if m := _DEF.match(line):
            name, in_signature = (m.group(1) if line[0] != "+" else ""), True
        if in_signature and name and line[:1] in ("+", "-"):
            names.add(name)
        if in_signature and line.rstrip().endswith(":"):
            in_signature = False
    return names


def uncovered(names: set[str], architecture: str) -> set[str]:
    """Return `names` unless `architecture` has a "Status: approved" line, else those it never mentions."""
    if not re.search(r"\bstatus:\s*approved\b", re.sub(r"[*_]", "", architecture), re.I):
        return set(names)
    return {n for n in names if not re.search(rf"\b{n}\b", architecture)}
