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
