"""Check that a quoted review excerpt really appears in the text it cites."""
from __future__ import annotations

from pathlib import Path


def _norm(s: str) -> str:
    return " ".join(s.split())


def quote_near(text: str, line: int, quote: str, slack: int = 2) -> bool:
    """True if the non-empty, whitespace-normalised quote appears in lines
    max(1, line-slack)..line+slack (1-based, clipped to the text) of text,
    joined by spaces. Case-sensitive; an empty quote is False."""
    lines = text.splitlines()
    window = lines[max(1, line - slack) - 1:max(0, line + slack)]
    return quote_in([" ".join(window)], quote)


def quote_in(texts: list[str], quote: str) -> bool:
    """True if the non-empty, whitespace-normalised quote appears in any one
    of the whitespace-normalised texts (each checked separately)."""
    q = _norm(quote)
    return bool(q) and any(q in _norm(t) for t in texts)


def _item_errors(option: str, it: object, facts: dict) -> list[str]:
    d = it if isinstance(it, dict) else {"id": it}; fid = d.get("id")
    if fid not in facts["fails"]:
        return [f"{fid}: not a failing finding"]
    if option == "overstated" and not str(d.get("reason") or "").strip():
        return [f"{fid}: empty reason"]
    if option != "wrong":
        return []
    text = facts["read"](str(d.get("file")))
    if fid in facts["capped"] or text is None:
        return [f"{fid}: capped, or file {d.get('file')} not found"]
    ok = isinstance(d.get("line"), int) and quote_near(text, d["line"], str(d.get("quote")))
    return [] if ok else [f"{fid}: quote not near line {d.get('line')} of {d.get('file')}"]


def _other_errors(option: str, ev: dict, facts: dict) -> list[str]:
    fails, g = facts.get("failures") or [], lambda k: str(ev.get(k) or "")
    if option == "tests_wrong":
        t = g("test")
        return ([f"{t}: not a failing test"] * (t not in fails)
                + [f"quote not in docs: {g('quote')}"] * (not quote_in(facts.get("docs") or [], g("quote"))))
    if option == "code_wrong":
        ids = ev.get("tests")
        bad = [str(t) for t in ids or [] if t not in fails] if isinstance(ids, list) else [""]
        return [f"tests: empty or not failing: {bad}"] if bad or not ids else []
    if option == "escalate":
        return [] if g("question").strip() else ["question: empty"]
    if option == "architecture_stop":
        p = Path(g("path"))
        p = p if p.is_absolute() else Path(facts.get("run") or ".") / p
        ok = g("path") and p.is_file() and p.match("architecture-change-*.md")
        return [] if ok else [f"{g('path')}: not an existing architecture-change-*.md"]
    ok = g("user_said").strip() and g("to") in (facts.get("resume") or [])
    return [] if ok else [f"user_continue: empty user_said or {g('to')} not in resume"]


def check_evidence(option: str, evidence: dict, facts: dict) -> list[str]:
    """Errors for a finding decision's evidence ([] when fine; never raises).
    evidence["findings"] must be a non-empty list: ids for "correct", {id,
    reason} for "overstated", {id, file, line, quote} for "wrong". Each id
    must be in facts["fails"]; reason non-blank; "wrong" ids not in
    facts["capped"], facts["read"](file) not None and quote_near holds.
    Errors name the id or file; unknown option: an error. Also (facts failures, docs, run, resume): "tests_wrong" {test, quote}:
    test in failures, quote in docs; "code_wrong" {tests}: non-empty, all in
    failures; "escalate" {question}: non-empty; "architecture_stop" {path}:
    existing architecture-change-*.md (absolute or under run); "user_continue"
    {user_said, to}: user_said non-empty, to in resume."""
    if option in ("tests_wrong", "code_wrong", "escalate", "architecture_stop", "user_continue"):
        return _other_errors(option, evidence if isinstance(evidence, dict) else {}, facts)
    if option not in ("correct", "overstated", "wrong"):
        return [f"unknown option: {option}"]
    items = evidence.get("findings") if isinstance(evidence, dict) else None
    if not isinstance(items, list) or not items:
        return ["findings: missing or empty"]
    return [e for it in items for e in _item_errors(option, it, facts)]
