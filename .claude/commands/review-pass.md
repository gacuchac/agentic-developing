---
description: Run one Codex review pass on the current changes
argument-hint: <plan|commit|principles|alternatives|answers-ask|pr> <task-id> [<commit sha or base>]
disable-model-invocation: true
---

Use the codex-reviewer subagent to run pass $0 for .claude/runs/$1/, giving it what that pass needs:
- `commit`, `principles`, `alternatives`: `--commit $2` (default: HEAD) and `--base dev`.
- `answers-ask`: `--base $2` (default: the task's launch hash, from its build board or the merge-base of dev and HEAD).
- `pr`: `--base $2` (default: `dev`).
- `plan`: nothing more.
Show me its output word for word, then give your own one-line assessment of whether you agree.
