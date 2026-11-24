"""Plain-text views of a task's state and of its decision log."""

from collections import Counter


def status_text(state: dict, last: int = 5) -> str:
    """Return the task line, the pending line and the last `last` history entries of a state."""
    head = " ".join(f"{k}={state.get(k)}" for k in ("task", "mode", "stage", "unit", "node", "round"))
    pending = state.get("pending") or {}
    lines = [head, "pending: " + " ".join(f"{k}={v}" for k, v in pending.items())]
    for e in state.get("history", [])[-last:] if last > 0 else []:
        lines.append(f"{e.get('node')} {e.get('outcome')} -> {e.get('to')} {e.get('error', '')}".rstrip())
    return "\n".join(lines)


def report_text(log: str) -> str:
    """Return Decisions, Dismissals, Commits and Ratchet candidates sections for the text of decisions.tsv."""
    rows = [line.split("\t") for line in log.splitlines()[1:] if line]
    rows = [r + [""] * (6 - len(r)) for r in rows]
    dismissed = [r for r in rows if r[2] in ("overstated", "wrong")]
    ids = Counter(i for r in dismissed for i in r[4].split("; ") if i)
    sections = {
        "Decisions": rows,
        "Dismissals": dismissed,
        "Commits": [r for r in rows if "commit" in r[1]],
    }
    out = [f"## {title}\n" + "\n".join(" | ".join(r) for r in rs) for title, rs in sections.items()]
    out.append("## Ratchet candidates\n" + "\n".join(i for i, n in ids.items() if n >= 2))
    return "\n".join(out)
