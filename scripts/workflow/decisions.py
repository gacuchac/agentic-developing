"""Pure helpers for the decision log (decisions.tsv)."""

HEADER = "ts\tphase\tdecision\twhy\tevidence\tresult"


def row(entry: dict) -> list[str]:
    """Map a history entry to the six decision-log columns: ts, phase, decision, why, evidence, result."""
    ev = entry.get("evidence") or {}
    findings = ev.get("findings", [])
    why = [str(f["quote"]) for f in findings if f.get("quote")]
    why = [*ev.get("reasons", []), *why] or [entry.get("message", "")]
    refs = [f"{f['file']}:{f['line']}" if f.get("file") else str(f.get("id", "")) for f in findings]
    refs += [*ev.get("tests", []), *filter(None, [entry.get("sha"), ev.get("path")])]
    return [
        entry.get("t", ""),
        f"u{entry.get('unit', '')} {entry.get('node', '')}",
        entry.get("decision") or entry.get("outcome", ""),
        "; ".join(why),
        "; ".join(refs),
        entry.get("to", ""),
    ]


def append_text(existing: str, cells: list[str]) -> str:
    """Return the log's new text: header first when empty, cells sanitised against tabs, newlines and formulas."""
    clean = [" ".join(c.replace("\t", " ").splitlines()) for c in cells]
    clean = ["'" + c if c[:1] in "=+-@" and c else c for c in clean]
    head = HEADER + "\n" if not existing else ""
    return existing + head + "\t".join(clean) + "\n"
