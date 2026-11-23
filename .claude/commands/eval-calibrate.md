---
description: Calibrate the eval judge against my own grades
argument-hint: <project> <run-id>
disable-model-invocation: true
---

1. Pick a few transcripts from $0/evals/runs/$1/, mixing passes and failures. Show me one at a time, with a short trace summary but without the judge's scores.
2. For each, ask me for a 1 to 5 score and a reason on tool_use, groundedness, answers_question and completeness. Save my grades to $0/evals/calibration/$1/<case-id>.json.
3. Compare my grades with the judge's scores.json, per dimension, in a small table.
4. Where we differ by more than 1 point, propose a specific change to the judge rubric: $0/.claude/review-passes/judge.md if the project has its own, else the workspace's. Apply it only if I say yes.
