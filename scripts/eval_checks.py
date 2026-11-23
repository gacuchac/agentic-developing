#!/usr/bin/env python3
"""Code checks for one eval run: tool-call count, redundant calls, token and time budgets."""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import yaml


def load_trace(path: Path) -> list[dict]:
    """Read trace.jsonl into a list of events."""
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def tool_calls(events: list[dict]) -> list[dict]:
    """Only the tool-call events."""
    return [e for e in events if e.get("type") == "tool_call"]


def redundant_calls(calls: list[dict]) -> list[str]:
    """Tool calls repeated with identical arguments."""
    keys = Counter(f"{c.get('tool')} {json.dumps(c.get('args', {}), sort_keys=True)}" for c in calls)
    return [key for key, count in keys.items() if count > 1]


def total_tokens(events: list[dict]) -> int:
    """Input plus output tokens over all model calls."""
    return sum(
        e.get("input_tokens", 0) + e.get("output_tokens", 0) for e in events if e.get("type") == "model_call"
    )


def elapsed_seconds(events: list[dict]) -> float:
    """Wall time from the first event to the last."""
    stamps = [e["ts"] for e in events if "ts" in e]
    return max(stamps) - min(stamps) if stamps else 0.0


def check(name: str, value: float, limit: float | None) -> dict:
    """One check result; no limit means it always passes."""
    passed = limit is None or value <= limit
    return {"check": name, "value": value, "limit": limit, "result": "PASS" if passed else "FAIL"}


def run_checks(events: list[dict], budgets: dict) -> list[dict]:
    """All code checks for one run, each reported separately."""
    calls = tool_calls(events)
    repeats = redundant_calls(calls)
    return [
        check("tool_calls", len(calls), budgets.get("max_tool_calls")),
        {**check("redundant_calls", len(repeats), 0), "details": repeats},
        check("total_tokens", total_tokens(events), budgets.get("max_total_tokens")),
        check("seconds", round(elapsed_seconds(events), 1), budgets.get("max_seconds")),
    ]


def main() -> int:
    if len(sys.argv) != 3:
        sys.exit("usage: eval_checks.py <run dir> <case file>")
    run_dir, case_file = Path(sys.argv[1]), Path(sys.argv[2])
    budgets = (yaml.safe_load(case_file.read_text()) or {}).get("budgets", {})
    results = run_checks(load_trace(run_dir / "trace.jsonl"), budgets)
    output = json.dumps(results, indent=2)
    (run_dir / "checks.json").write_text(output)
    print(output)
    return 0 if all(r["result"] == "PASS" for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
