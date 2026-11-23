"""Deterministic slop checks over Python source text: justifying comments, hidden state, banned imports."""

from __future__ import annotations

import ast
import io
import re
import tokenize

Finding = tuple[int, str]

JUSTIFICATION = re.compile(r"\b(workaround|for now|hack|temporary|temporarily|in case|quick fix)\b", re.IGNORECASE)


def justification_comments(source: str) -> list[Finding]:
    """Return (line, SLOP001 message) for each comment that justifies a workaround."""
    message = "SLOP001 comment justifies a workaround: fix the cause or delete the comment"
    findings = []
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.COMMENT and JUSTIFICATION.search(token.string):
            findings.append((token.start[0], message))
    return findings


def banned_imports(source: str, banned: set[str]) -> list[Finding]:
    """Return (line, SLOP003 message) for each import whose top-level module is in banned."""
    findings = []
    for node in ast.walk(ast.parse(source)):
        for module in imported_modules(node):
            top = module.split(".")[0]
            if top in banned:
                message = f"SLOP003 {top} imported in a pure module: move the I/O to the caller"
                findings.append((node.lineno, message))
    return sorted(findings)


def imported_modules(node: ast.AST) -> list[str]:
    """Return the module names an import statement brings in, or [] for any other node."""
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
        return [node.module]
    return []
