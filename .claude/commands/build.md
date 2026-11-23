---
description: Build a planned product or large feature from its PRD, with just-in-time decomposition
argument-hint: <planner task-id>
disable-model-invocation: true
---

PRD: .claude/runs/$0/planner/06-prd.md
Build board: .claude/runs/$0/build-board.md

Start or resume:
- If the build board exists, read it, tell me where things stand, and carry on. Check every task marked planning, building or merging against its run folder, worktree and branch before trusting the mark.
- Otherwise write the board from the PRD's big tasks and their dependencies, every task waiting. Show it to me and wait for my go.

Before each round, check that the main checkout is on dev, clean and up to date (section 4b). If it isn't clean, stop and ask me.

Then repeat the build loop in .claude/workflow/loop.md until every task is merged or blocked:
1. Mark ready every waiting task whose dependencies are all merged into dev. Plan only ready tasks.
2. Plan: decompose the ready tasks, at most 3 at a time, cross-check the plans against each other and against tasks still building, review them, and write eval cases with me where flagged.
3. Build: launch one workflow orchestrator per checked plan, never more than 3 subagents at once. Build Mode C tasks in this session, one at a time.
4. Merge each finished branch into dev, then go back to 1.
Update the board after every change of status.

If a task is blocked, tell me which and why, and keep building the tasks that don't depend on it.
When every task is merged: have qa run the full suite on dev, promote dev to uat (section 4b), and give me a short summary per task.
