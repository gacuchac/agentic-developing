"""SubagentStop hook: record a workflow agent's `workflow-result` block against the pending step."""

from __future__ import annotations

import json
import re

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
