"""SubagentStop hook: record a workflow agent's `workflow-result` block against the pending step."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKSPACE / "scripts" / "workflow"))

from effects import claimfiles  # noqa: E402

BLOCK = re.compile(r"```workflow-result\s*\n(.*?)\n\s*```", re.DOTALL)
STEP_LINE = re.compile(r"^wf-step:\s*(\S+)", re.MULTILINE)
RUN_LINE = re.compile(r"^Run folder:\s*(\S+)", re.MULTILINE)


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


def engine_python(workspace: Path) -> str:
    """Return `<workspace>/.venv/bin/python` when that file exists, else "python3"."""
    venv = workspace / ".venv" / "bin" / "python"
    return str(venv) if venv.exists() else "python3"


def real_record(run: Path, step_id: str, result: dict) -> list[str]:
    """Run `wf record <run> <step_id>` with `result`; return the refusal lines, empty when accepted."""
    with tempfile.NamedTemporaryFile("w", suffix=".json") as handle:
        json.dump(result, handle)
        handle.flush()
        wf = WORKSPACE / "scripts" / "workflow" / "wf.py"
        command = [engine_python(WORKSPACE), str(wf), "record", str(run), step_id, handle.name]
        done = subprocess.run(command, capture_output=True, text=True)
    return done.stderr.splitlines() if done.returncode else []


def _prompt_of(transcript: Path) -> str:
    """Return the text of the first user record of the JSONL `transcript`, or "" when there is none."""
    for line in transcript.read_text().splitlines():
        message = json.loads(line).get("message") or {}
        if message.get("role") == "user":
            content = message.get("content")
            return content if isinstance(content, str) else "".join(part.get("text", "") for part in content)
    return ""


def _transcript_messages(transcript: Path) -> list[str]:
    """Return the texts of the assistant records of the JSONL `transcript`, in order: text parts and hand-back calls."""
    texts = []
    for line in transcript.read_text().splitlines():
        message = json.loads(line).get("message") or {}
        parts = message.get("content")
        if message.get("role") != "assistant" or not isinstance(parts, list):
            continue
        for part in parts:
            if part.get("type") == "text":
                texts.append(part.get("text") or "")
            elif part.get("type") == "tool_use" and part.get("name") == "SubagentHandback":
                texts.append((part.get("input") or {}).get("message") or "")
    return texts


def _transcript_result(event: dict) -> dict | None:
    """Return the last valid `workflow-result` block in the assistant records of the event's transcript, or None."""
    if not event.get("agent_transcript_path"):
        return None
    results = (extract_result(text) for text in reversed(_transcript_messages(Path(event["agent_transcript_path"]))))
    return next((r for r in results if r is not None), None)


def _is_pending(run: Path, step_id: str, agent_type: str | None) -> bool:
    """Return True when `run`'s state is pending the agent step `step_id` for `agent_type`."""
    pending = (json.loads((run / "state.json").read_text()).get("pending")) or {}
    return pending.get("kind") == "agent" and pending.get("agent") == agent_type and pending.get("step_id") == step_id


def _agent_transcript(event: dict) -> Path | None:
    """Return the agent's transcript path: `agent_transcript_path` when set, else on `PreToolUse` the agent's file
    under the session's `subagents/` folder, else None. Does no I/O."""
    if event.get("agent_transcript_path"):
        return Path(event["agent_transcript_path"])
    if event.get("hook_event_name") == "PreToolUse" and event.get("transcript_path") and event.get("agent_id"):
        return Path(event["transcript_path"]).with_suffix("") / "subagents" / f"agent-{event['agent_id']}.jsonl"
    return None


def _from_prompt(event: dict, active: Path, transcript: Path) -> tuple[Path, str] | None:
    """Return (run, step id) named in the agent's own prompt when this session holds that run and it is pending."""
    prompt = _prompt_of(transcript)
    step_id = step_id_of(prompt)
    match = RUN_LINE.search(prompt)
    if step_id is None or match is None:
        return None
    run = Path(match.group(1))
    claims = (claimfiles.read(active, p.name) or {} for p in active.glob("*.json"))
    held = any(c.get("run") == str(run) and c.get("session") == event.get("session_id") for c in claims)
    return (run, step_id) if held and _is_pending(run, step_id, event.get("agent_type")) else None


def _pending_step(event: dict, active: Path, transcript: Path | None) -> tuple[Path, str] | None:
    """Return (run folder, step id) the agent reports for: its registry entry, else the prompt in its transcript.

    The step must be pending for the agent type; a prompt's run must also be held by the event's session."""
    entry = claimfiles.read(active / "agents", f"{event.get('agent_id')}.json")
    if entry:
        run = Path(entry["run"])
        return (run, entry["step_id"]) if _is_pending(run, entry["step_id"], event.get("agent_type")) else None
    return _from_prompt(event, active, transcript) if transcript is not None else None


def _log(
    active: Path,
    event: dict,
    transcript: Path | None,
    pending: tuple[Path, str] | None,
    result: dict | None,
    outcome: str,
) -> None:
    """Append one JSON line describing this event and its outcome to `<active>/recorder.log`; skip when unwritable."""
    line = {
        "ts": datetime.now().astimezone().isoformat(),
        "event": event.get("hook_event_name") or "",
        "agent_id": event.get("agent_id") or "",
        "agent_type": event.get("agent_type") or "",
        "session": event.get("session_id") or "",
        "transcript": bool(event.get("agent_transcript_path")),
        "agent_transcript": str(transcript) if transcript else "",
        "step": [str(pending[0]), pending[1]] if pending else None,
        "result": result is not None,
        "outcome": outcome,
    }
    try:
        with (active / "recorder.log").open("a") as handle:
            handle.write(json.dumps(line) + "\n")
    except Exception:
        pass


def main(stdin: str, active: Path, record: Callable[[Path, str, dict], list[str]]) -> int:
    """Record the result block of a stopping workflow agent; return 2 with the refusal on stderr, else 0.

    `record(run, step_id, result)` returns error lines. It records from the registry entry, else from the
    agent's prompt in its transcript (`agent_transcript_path`, or on `PreToolUse` the agent's file under the
    session's `subagents/` folder); missing or invalid input, no step found, no pending step, no claim held
    by this session, or no valid block records nothing. Each call appends one line to `<active>/recorder.log`
    with the outcome; logging never changes the return value."""
    event: dict = {}
    pending = result = transcript = None
    try:
        event = json.loads(stdin)
        transcript = _agent_transcript(event)
        pending = _pending_step(event, active, transcript)
        result = (
            extract_result(event.get("last_assistant_message") or "")
            or extract_result(event.get("tool_input", {}).get("message") or "")
            or _transcript_result(event)
        )
    except Exception:
        missing = transcript is not None and not transcript.exists()
        _log(
            active,
            event if isinstance(event, dict) else {},
            transcript,
            pending,
            result,
            "no transcript" if missing else "bad input",
        )
        return 0
    if pending is None or result is None:
        _log(active, event, transcript, pending, result, "no step" if pending is None else "no result")
        return 0
    errors = record(pending[0], pending[1], result)
    if errors:
        print("\n".join(errors), file=sys.stderr)
    _log(active, event, transcript, pending, result, "refused" if errors else "recorded")
    return 2 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.stdin.read(), WORKSPACE / ".claude" / "runs" / ".active", real_record))
