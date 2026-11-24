"""SubagentStop hook: record a workflow agent's `workflow-result` block against the pending step."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKSPACE / "scripts" / "workflow"))

from effects import claimfiles  # noqa: E402

BLOCK = re.compile(r"```workflow-result\s*\n(.*?)\n\s*```", re.DOTALL)
STEP_LINE = re.compile(r"^wf-step:\s*(\S+)", re.MULTILINE)


def extract_result(message: str) -> dict | None:
    """Return the JSON inside the last `workflow-result` fenced block of `message`, or None when absent or invalid."""
    blocks = BLOCK.findall(message)
    try:
        return json.loads(blocks[-1]) if blocks else None
    except ValueError:
        return None


def step_id_of(prompt_text: str) -> str | None:
    """Return the id on the `wf-step: <id>` line of `prompt_text`, or None."""
    match = STEP_LINE.search(prompt_text)
    return match.group(1) if match else None


def real_record(run: Path, step_id: str, result: dict) -> list[str]:
    """Run `wf record <run> <step_id>` with `result`; return the refusal lines, empty when accepted."""
    with tempfile.NamedTemporaryFile("w", suffix=".json") as handle:
        json.dump(result, handle)
        handle.flush()
        wf = WORKSPACE / "scripts" / "workflow" / "wf.py"
        done = subprocess.run(
            ["python3", str(wf), "record", str(run), step_id, handle.name], capture_output=True, text=True
        )
    return done.stderr.splitlines() if done.returncode else []


def _pending_step(event: dict, active: Path) -> tuple[Path, str] | None:
    """Return (run folder, step id) when the stopping agent is the one the session's pending step waits for."""
    names = claimfiles.owned_by(active, event.get("session_id"))
    if not names:
        return None
    run = Path(claimfiles.read(active, names[0])["run"])
    pending = (json.loads((run / "state.json").read_text()).get("pending")) or {}
    if pending.get("kind") != "agent" or pending.get("agent") != event.get("agent_type"):
        return None
    return run, pending["step_id"]


def main(stdin: str, active: Path, record: Callable[[Path, str, dict], list[str]]) -> int:
    """Record the result block of a stopping workflow agent; return 2 with the refusal on stderr, else 0.

    `record(run, step_id, result)` returns error lines. Missing or invalid input, no claim,
    no pending step for this agent, or no valid block records nothing."""
    try:
        event = json.loads(stdin)
        pending = _pending_step(event, active)
        result = extract_result(event.get("last_assistant_message") or "") or extract_result(
            event.get("tool_input", {}).get("message") or ""
        )
    except Exception:
        return 0
    if pending is None or result is None:
        return 0
    errors = record(pending[0], pending[1], result)
    if errors:
        print("\n".join(errors), file=sys.stderr)
    return 2 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.stdin.read(), WORKSPACE / ".claude" / "runs" / ".active", real_record))
