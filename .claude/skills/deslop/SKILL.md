---
name: deslop
description: "Remove AI code slop from a branch's diff without changing behaviour: narrating comments, defensive checks on trusted paths, needless layers, duplication, dead code. Use before opening a PR, for the subtract unit, or for /deslop."
---

# Deslop

Adapted from Cursor's `deslop` skill (cursor-team-kit, MIT) and pstack's subtract-before-you-add and minimize-reader-load principles by Lauren Tan (MIT). See `.claude/skills/THIRD_PARTY.md`.

Scope: the given files or diff; otherwise the branch's diff against `dev`.

Remove, without changing behaviour:
- Comments that narrate the code, justify a workaround, or repeat the docstring. Keep contract docstrings on public functions and comments about constraints imposed from outside (vendor, protocol, platform).
- Defensive checks, `try`/`except` and fallbacks on paths whose inputs are already trusted or validated at the boundary.
- Layers that only forward: one-caller wrappers, adapters with one implementation, pass-through functions. Inline them.
- Duplicated logic: put the decision in one place and call it.
- Dead code, unused parameters, speculative options nothing uses.
- Crammed lines (semicolons, long one-liners): give each statement its own line.

Rules:
- Behaviour stays the same: the full suite passes before and after, and no test changes.
- Smallest edits that remove the slop; no rewrites, no new abstractions.
- A public signature change is an architecture change: stop and report it instead.
- Report in 1–3 sentences: what was removed, line delta, suite result.
