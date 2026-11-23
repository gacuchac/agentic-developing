"""Deterministic slop checks over Python source text: justifying comments, hidden state, banned imports."""

from __future__ import annotations

import io
import re
import tokenize

Finding = tuple[int, str]

JUSTIFICATION = re.compile(r"workaround|for now|hack|temporary|temporarily|in case|quick fix", re.IGNORECASE)


def justification_comments(source: str) -> list[Finding]:
    """Return (line, SLOP001 message) for each comment that justifies a workaround."""
    message = "SLOP001 comment justifies a workaround: fix the cause or delete the comment"
    findings = []
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.COMMENT and JUSTIFICATION.search(token.string):
            findings.append((token.start[0], message))
    return findings
