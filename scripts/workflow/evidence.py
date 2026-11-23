"""Check that a quoted review excerpt really appears in the text it cites."""
from __future__ import annotations


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


def check_evidence(option: str, evidence: dict, facts: dict) -> list[str]:
    """Errors for a finding decision's evidence ([] when fine; never raises).
    evidence["findings"] must be a non-empty list: ids for "correct", {id,
    reason} for "overstated", {id, file, line, quote} for "wrong". Each id
    must be in facts["fails"]; reason non-blank; "wrong" ids not in
    facts["capped"], facts["read"](file) not None and quote_near holds.
    Errors name the id or file. Unknown option: an error."""
    if option not in ("correct", "overstated", "wrong"):
        return [f"unknown option: {option}"]
    items = evidence.get("findings") if isinstance(evidence, dict) else None
    if not isinstance(items, list) or not items:
        return ["findings: missing or empty"]
    return [e for it in items for e in _item_errors(option, it, facts)]
