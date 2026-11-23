---
description: Calibrate the eval judge against my own grades
argument-hint: <run-id>
disable-model-invocation: true
---

1. Pick a few transcripts from evals/runs/$0/, mixing passes and failures. Show me one at a time, with a short trace summary but without the judge's scores.
2. For each, ask me for a 1 to 5 score and a reason on tool_use, groundedness, answers_question and completeness. Save my grades to evals/calibration/$0/<case-id>.json.
3. Compare my grades with the judge's scores.json, per dimension, in a small table.
4. Where we differ by more than 1 point, propose a specific change to .claude/review-passes/judge.md. Apply it only if I say yes.
