---
description: Plan a new product or large feature risk-first, from context and research to PRD, checking in after every step
argument-hint: <project>/<task-id> <description of the product or feature>
disable-model-invocation: true
---

Planning folder: .claude/runs/$0/planner/

Start or resume:
- If the folder exists, read progress.md, tell me the last finished step, and continue from the next one. Never redo a finished step unless I ask.
- Otherwise create it, write my request ($ARGUMENTS, whose first word is the task-id) verbatim to request.md, and start at step 0.

Step 0, context (yours; a subagent can't talk to me). Before any research, ask me what the request doesn't already answer, a few questions at a time, and write each answer in my words to 00-context.md as I give it. Every later step reads that file. Cover:
1. **Project.** An existing subfolder of ~/Developing, or a new project (then run `python3 ~/Developing/scripts/new_project.py --help` and create it after I confirm the name).
2. **Outcome.** What the finished thing must show, to whom, and by when. What is explicitly out of scope.
3. **Deployment.** Whether it runs only on this machine or must be reachable elsewhere; if elsewhere: which service and account, which environment (one for a proof of concept, or dev, uat and production), the URL or domain if there is one, and who says go for each deploy. Nothing is deployed without my go.
4. **Resources.** External services and APIs it may use; which credentials already exist and where they live (the name of the env var or file, never the value); spending limits for APIs and hosting; the data it needs and where it comes from; which models it may call.
5. **Seams.** Anything it must cross that only shows in the real environment: sign-in, network and firewall rules, DNS and TLS, secrets, operating-system permissions, hardware, other people's APIs.
6. **Constraints.** Stack choices beyond the workspace defaults, privacy and data handling, things that must not be touched, and whether it changes LLM or agent behaviour (then it needs eval cases).
When I say the context is complete, record step 0 in progress.md and go to step 1.

For steps 1, 2, 3, 4 and 6:
1. Call the planner subagent with the task-id and the step number, and wait for it to finish.
2. Give me the path of the file it wrote and ask me to read it in full; I review the file, not your summary. Add at most 5 lines on what to look at.
3. Append a line to progress.md: step number, file name, time, one-line summary.
4. Ask me whether to go on, change something in this step, or stop. Go to the next step only when I say so.

Risk tasks, between step 4 and step 5 (yours). Step 4 ends with the risk tasks: the seams still risky enough to build for real before the solution is fixed, in build order. If it lists none, write that in 04-risk-tasks.md, ask me "risks retired?", and go to step 5 on my yes. Otherwise, for each risk task in order:
1. Build it as a task of its own through the build loop in .claude/workflow/loop.md, on its own branch, with every gate. Its first unit is the seam's smoke check with fixed assertions, seen to fail and then made to pass. No code skips the gates because it was written during planning.
2. Merge it into dev. If 00-context.md names a target environment, ask for my go, deploy there, and run the seam's smoke check against it. Logs and transcripts are the evidence; the fixed assertions decide pass or fail.
3. Append to 04-risk-tasks.md: the seam, the branch and merge commit, the smoke check's command and result, and where the evidence is.
4. A seam that fails: show me the evidence and decide with it. A fix goes back to the same task. A pivot is my decision; on my yes, go back to step 2 with the evidence.
When every seam passes, ask me "risks retired?". Go to step 5 only on my yes, and record it in progress.md.

For step 5, refine the solution with me (a subagent can't talk to me, so this part is yours):
1. Call the planner subagent for step 5 "draft". It writes 05-solution-draft.md.
2. Work through the draft with me here, one question at a time: the solution architecture, the software architecture (load the architecture skill for contracts and module boundaries) and the process flow diagram for each user story.
3. After each of my answers, append the decision in my words to 05-decisions.md, so a crash loses nothing. Apart from 00-context.md and 04-risk-tasks.md, that log is the only file you write; the planner writes every step file itself.
4. When I say the refinement is done, call the planner subagent for step 5 "finalize". It writes 05-solution.md. Point me to it to read in full, with at most 5 lines on what to look at, then record step 5 in progress.md.

After step 6, point me to 06-prd.md to read in full, then ask whether to start `/build $0`.
