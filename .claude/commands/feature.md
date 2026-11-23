---
description: Classify a feature or bug and run it through the right workflow mode
argument-hint: [simple:|parallel:|sequential:|interview:] <feature or bug description>
---

Task: $ARGUMENTS

Follow the routing rules in CLAUDE.md and .claude/workflow/loop.md.
1. Give the task a short task-id and create .claude/runs/<task-id>/ask.md with the task verbatim.
2. State the mode in one line, with the reason. If the task starts with `interview:`, use the interview route in section 3b of .claude/workflow/loop.md instead of Mode A, B or C, and skip steps 4 and 5 below.
3. Check that the main checkout is on dev, clean and up to date (section 4b). If it isn't clean, stop and ask me.
4. Mode A: create feature/<task-id> (bugfix/<task-id> for a bug) off dev, run the Mode A route, then merge it into dev by PR.
5. Mode B or C: split the task into tasks with their dependencies (one task if it can't be split), write them to .claude/runs/<task-id>/build-board.md, and run the build loop: Plan, then Build (workflow orchestrators in Mode B, this session in Mode C), then Merge.
6. Finish with a short summary: what was built, tests, eval results, review verdicts, PRs merged, anything left for me.
