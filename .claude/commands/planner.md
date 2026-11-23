---
description: Plan a new product or large feature in six steps, from research to PRD, checking in after every step
argument-hint: <task-id> <description of the product or feature>
disable-model-invocation: true
---

Planning folder: .claude/runs/$0/planner/

Start or resume:
- If the folder exists, read progress.md, tell me the last finished step, and continue from the next one. Never redo a finished step unless I ask.
- Otherwise create it, write my request ($ARGUMENTS, whose first word is the task-id) verbatim to request.md, and start at step 1.

For steps 1, 2, 3, 4 and 6:
1. Call the planner subagent with the task-id and the step number, and wait for it to finish.
2. Give me the path of the file it wrote and ask me to read it in full; I review the file, not your summary. Add at most 5 lines on what to look at.
3. Append a line to progress.md: step number, file name, time, one-line summary.
4. Ask me whether to go on, change something in this step, or stop. Go to the next step only when I say so.

For step 5, refine the solution with me (a subagent can't talk to me, so this part is yours):
1. Call the planner subagent for step 5 "draft". It writes 05-solution-draft.md.
2. Work through the draft with me here, one question at a time: the solution architecture, the software architecture (load the architecture skill for contracts and module boundaries) and the process flow diagram for each user story.
3. After each of my answers, append the decision in my words to 05-decisions.md, so a crash loses nothing. That log is the only file you write; the planner writes every step file itself.
4. When I say the refinement is done, call the planner subagent for step 5 "finalize". It writes 05-solution.md. Point me to it to read in full, with at most 5 lines on what to look at, then record step 5 in progress.md.

After step 6, point me to 06-prd.md to read in full, then ask whether to start `/build $0`.
