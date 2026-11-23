---
name: light-build
description: Light, interview-mode build of one feature or bug (one decomposer, two human checkpoints, a review of each commit plus one answers-ask pass, one fix round) for a time-boxed demo. Use when the user says "light build", "quick build", "interview build" or "build it light". Not for the full Simple, Parallel or Sequential loop.
argument-hint: <feature or bug description>
---

Task: use $ARGUMENTS if I used the slash command, otherwise what I just asked for.

Follow the interview route in section 3b of .claude/workflow/loop.md exactly, the same as `/feature interview: <task>`: give the task a short task-id, say in one line that this is the short route and the full process is the one above, and keep both checkpoints (I approve the plan; confirm the tests fail for the right reason). If a PRD from the light planner exists, build its tasks one at a time in dependency order, each with this route.
