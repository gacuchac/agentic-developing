"""Deterministic slop checks over Python source text: justifying comments, hidden state, banned imports."""

from __future__ import annotations

import ast
import io
import re
import sys
import tokenize
from pathlib import Path

Finding = tuple[int, str]

JUSTIFICATION = re.compile(r"\b(workaround|for now|hack|temporary|temporarily|in case|quick fix)\b", re.IGNORECASE)

LIST_MUTATORS = {"append", "extend", "insert", "pop", "clear", "remove"}

SET_AND_DICT_MUTATORS = {"add", "discard", "update", "setdefault", "popitem"}

MUTATING_METHODS = LIST_MUTATORS | SET_AND_DICT_MUTATORS

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


def hidden_state(source: str) -> list[Finding]:
    """Return (line, SLOP002 message) for global/nonlocal statements and functions that mutate module-level names."""
    tree = ast.parse(source)
    module_names = module_level_names(tree)
    findings = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Global, ast.Nonlocal)):
            names = ", ".join(node.names)
            findings.append((node.lineno, mutation_message(names)))
        if isinstance(node, FUNCTION_NODES):
            findings.extend(function_mutations(node, module_names))
    return sorted(set(findings))


def mutation_message(name: str) -> str:
    """Return the SLOP002 message for a function that mutates module state name."""
    return f"SLOP002 function mutates module state {name}: pass it in and return the result"


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


def local_names(function: ast.FunctionDef | ast.AsyncFunctionDef, nodes: list[ast.AST]) -> set[str]:
    """Return the parameters and plainly assigned names of a function; augmented targets do not bind."""
    arguments = function.args
    every_argument = arguments.posonlyargs + arguments.args + arguments.kwonlyargs
    names = {argument.arg for argument in every_argument}
    for extra in (arguments.vararg, arguments.kwarg):
        if extra is not None:
            names.add(extra.arg)
    augmented = {id(node.target) for node in nodes if isinstance(node, ast.AugAssign)}
    for node in nodes:
        is_store = isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)
        if is_store and id(node) not in augmented:
            names.add(node.id)
    return names


def root_name(node: ast.AST) -> str | None:
    """Return the name at the base of an attribute or subscript chain, or None if there is none."""
    while isinstance(node, (ast.Attribute, ast.Subscript)):
        node = node.value
    return node.id if isinstance(node, ast.Name) else None


def flat_targets(targets: list[ast.AST]) -> list[ast.AST]:
    """Return targets with tuple, list and starred targets expanded into their elements."""
    flat: list[ast.AST] = []
    for target in targets:
        if isinstance(target, (ast.Tuple, ast.List)):
            flat.extend(flat_targets(target.elts))
        elif isinstance(target, ast.Starred):
            flat.extend(flat_targets([target.value]))
        else:
            flat.append(target)
    return flat


def mutated_name(node: ast.AST) -> str | None:
    """Return the name a statement or call node writes to, or None if it writes to none."""
    targets: list[ast.AST] = []
    if isinstance(node, ast.Assign):
        targets = [t for t in flat_targets(node.targets) if not isinstance(t, ast.Name)]
    elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
        targets = [node.target]
    elif isinstance(node, ast.Delete):
        targets = node.targets
    elif isinstance(node, ast.Call):
        is_mutator = isinstance(node.func, ast.Attribute) and node.func.attr in MUTATING_METHODS
        return root_name(node.func.value) if is_mutator else None
    for target in targets:
        name = root_name(target)
        if name is not None:
            return name
    return None


def function_mutations(function: ast.FunctionDef | ast.AsyncFunctionDef, module_names: set[str]) -> list[Finding]:
    """Return SLOP002 findings for writes inside function to module-level names it does not bind locally."""
    nodes = own_nodes(function)
    local = local_names(function, nodes)
    findings = []
    for node in nodes:
        name = mutated_name(node)
        if name in module_names and name not in local:
            findings.append((node.lineno, mutation_message(name)))
    return findings


def check_source(source: str, path: Path) -> list[Finding]:
    """Return all findings for Python source text, with the banned-import check when path is under scripts/workflow/."""
    findings = justification_comments(source) + hidden_state(source)
    if path.parent.parts[-2:] == ("scripts", "workflow"):
        findings += banned_imports(source, {"subprocess"})
    return sorted(findings)


def check_file(path: Path) -> list[Finding]:
    """Return all findings for one Python file, with the banned-import check for scripts/workflow/ paths."""
    return check_source(path.read_text(), path)


def main(argv: list[str]) -> int:
    """Print `path:line: message` for each finding in the given .py files; return 1 if any, else 0."""
    found = False
    for argument in argv:
        if not argument.endswith(".py"):
            continue
        for line, message in check_file(Path(argument)):
            print(f"{argument}:{line}: {message}")
            found = True
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
