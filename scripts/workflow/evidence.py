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


_FIELDS = {"overstated": ("reason",), "wrong": ("file", "quote"), "tests_wrong": ("test", "quote"),
           "escalate": ("question",), "architecture_stop": ("path",), "user_continue": ("user_said", "to")}


def _bad(option: str, ev: dict) -> list[str]:
    """Errors for each text field of option that is not a non-empty str."""
    return [f"{k}: must be non-empty text" for k in _FIELDS.get(option, ())
            if not (isinstance(ev.get(k), str) and ev[k].strip())]


def _item_errors(option: str, it: object, facts: dict) -> list[str]:
    d = it if isinstance(it, dict) else {"id": it}; fid = d.get("id")
    if fid not in facts["fails"]:
        return [f"{fid}: not a failing finding"]
    errs = _bad(option, d) + ["line: must be an int"] * (option == "wrong" and type(d.get("line")) is not int)
    if errs or option != "wrong":
        return [f"{fid}: {e}" for e in errs]
    text = facts["read"](str(d.get("file")))
    if fid in facts["capped"] or text is None:
        return [f"{fid}: capped, or file {d.get('file')} not found"]
    ok = isinstance(d.get("line"), int) and quote_near(text, d["line"], str(d.get("quote")))
    return [] if ok else [f"{fid}: quote not near line {d.get('line')} of {d.get('file')}"]


def _tests_wrong(ev: dict, facts: dict) -> list[str]:
    t, q = ev["test"], ev["quote"]
    return ([f"{t}: not a failing test"] * (t not in (facts.get("failures") or []))
            + [f"quote not in docs: {q}"] * (not quote_in(facts.get("docs") or [], q)))


def _code_wrong(ev: dict, facts: dict) -> list[str]:
    ids = ev.get("tests")
    bad = [str(t) for t in ids if t not in (facts.get("failures") or [])] if isinstance(ids, list) else [""]
    return [f"tests: empty or not failing: {bad}"] if bad or not ids else []


def _architecture_stop(ev: dict, facts: dict) -> list[str]:
    p = Path(ev["path"])
    p = p if p.is_absolute() else Path(facts.get("run") or ".") / p
    ok = p.is_file() and p.match("architecture-change-*.md")
    return [] if ok else [f"{ev['path']}: not an existing architecture-change-*.md"]


def _user_continue(ev: dict, facts: dict) -> list[str]:
    ok = ev["to"] in (facts.get("resume") or [])
    return [] if ok else [f"to: {ev['to']} not in resume"]


_OTHER = {"tests_wrong": _tests_wrong, "code_wrong": _code_wrong, "escalate": lambda ev, facts: [],
          "architecture_stop": _architecture_stop, "user_continue": _user_continue}


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
    if option in _OTHER:
        ev = evidence if isinstance(evidence, dict) else {}
        return _bad(option, ev) or _OTHER[option](ev, facts)
    if option not in ("correct", "overstated", "wrong"):
        return [f"unknown option: {option}"]
    items = evidence.get("findings") if isinstance(evidence, dict) else None
    if not isinstance(items, list) or not items:
        return ["findings: missing or empty"]
    return [e for it in items for e in _item_errors(option, it, facts)]
