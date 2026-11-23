---
name: light-planner
description: Light, interview-mode planning in three steps (scope and options, test and choose, solution and PRD) that takes minutes instead of hours. Use when the user says "light planner", "light plan", "quick plan", "interview planning", or asks for a short or fast version of planning for a time-boxed demo. Not for the full six-step /planner.
argument-hint: <task-id> <description of the product or feature>
---

Task-id and request: if I gave a task-id, use it; otherwise make a short one from my request and tell me what it is. Planning folder: .claude/runs/<task-id>/planner/

This is the short version of /planner for time-boxed demos. Say once, in a line, that the full six-step /planner is the normal process. Be brief: no more than 5 lines on what to look at after each step.

Start or resume:
- If the folder exists, read progress.md, tell me the last finished step, and continue from the next one. Never redo a finished step unless I ask.
- Otherwise create it, write my request verbatim to request.md (from $ARGUMENTS if I used the slash command, otherwise from what I said), and start at I1.

Step I1 (scope and options):
1. Call the planner subagent with the task-id and step "I1", and wait.
2. Give me the path of 01-scope-options.md. I skim it. Append a line to progress.md (step, file, time, one-line summary). Ask whether to go on.

Step I2 (test and choose):
1. Call the planner subagent with step "I2", and wait.
2. Give me the path of 02-chosen.md and say in two lines what was tested and what was chosen. This is the checkpoint where I decide. Append to progress.md and ask whether to go on.

Step I3 (solution and PRD), in two parts:
1. Ask me 3 to 5 questions, one at a time, about the choices that matter most (architecture, contracts, scope). Use the architecture skill for contracts. After each answer, append my decision in my words to 03-decisions.md. That is the only file you write besides progress.md.
2. When I say we're done, call the planner subagent with step "I3". It writes 03-solution-prd.md. Point me to it to read, with at most 5 lines on what to look at. Record it in progress.md.

Then ask whether to start `/build <task-id>`.
