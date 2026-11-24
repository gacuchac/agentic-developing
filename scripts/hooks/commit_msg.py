#!/usr/bin/env python3
"""commit-msg check: the subject must be US-n:, test(US-n): or X<n>: with text."""

from __future__ import annotations

import re
import sys
from pathlib import Path

_STORIES = r"US-\d+(?:, US-\d+)*"
SUBJECT = re.compile(rf"({_STORIES}|test\({_STORIES}\)|X\d+)( \(\d+/\d+\))?: \S")


def valid_subject(subject: str) -> bool:
    """True for a US-n, test(US-n) or X<n> subject with text, or a Merge or Revert subject."""
    return subject.startswith(("Merge ", "Revert ")) or SUBJECT.match(subject) is not None


def main(argv: list[str]) -> int:
    """Check the first line of the message file argv[0]; return 0 if valid, else print a hint and return 1."""
    lines = Path(argv[0]).read_text().splitlines()
    subject = lines[0] if lines else ""
    if valid_subject(subject):
        return 0
    print(f"commit message must start with US-n:, test(US-n): or X<n>: (got: {subject})", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
