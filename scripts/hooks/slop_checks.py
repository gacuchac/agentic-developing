"""Deterministic slop checks over Python source text: justifying comments, hidden state, banned imports."""

from __future__ import annotations

import ast
import io
import re
import tokenize

Finding = tuple[int, str]

JUSTIFICATION = re.compile(r"\b(workaround|for now|hack|temporary|temporarily|in case|quick fix)\b", re.IGNORECASE)

FUNCTION_NODES = (ast.FunctionDef, ast.AsyncFunctionDef)


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


def module_level_names(tree: ast.Module) -> set[str]:
    """Return the names bound by top-level assignments of a module."""
    names = set()
    for statement in tree.body:
        if isinstance(statement, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            names.update(stored_names(statement))
    return names


def stored_names(node: ast.AST) -> set[str]:
    """Return every plain name stored anywhere inside node."""
    return {child.id for child in ast.walk(node) if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Store)}


def own_nodes(function: ast.AST) -> list[ast.AST]:
    """Return the nodes of a function body, without entering nested functions."""
    found = []
    pending = list(ast.iter_child_nodes(function))
    while pending:
        node = pending.pop()
        found.append(node)
        if not isinstance(node, FUNCTION_NODES):
            pending.extend(ast.iter_child_nodes(node))
    return found
