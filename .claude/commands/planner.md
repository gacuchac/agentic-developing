---
description: Plan a new product or large feature risk-first, from context and research to PRD, checking in after every step
argument-hint: <description of the product or feature>   (to resume: <project>/<plan-id>, or nothing)
disable-model-invocation: true
---

My input: $ARGUMENTS

A plan lives in the project's own repo: `~/Developing/<project>/docs/planning/<plan-id>/`. That is "the planning folder" below. Everything a plan produces is written there; nothing of it is kept in the workspace.

Start or resume:
- **No input:** list every `~/Developing/*/docs/planning/*/progress.md` with its last line, and ask me which plan to resume or what to plan.
- **The input's first word is `<project>/<plan-id>` and that planning folder exists:** read its progress.md, tell me the last finished step, and continue from the next one. Never redo a finished step unless I ask.
- **Anything else is a new request.** I don't have to name a project or an id; step 0 settles both.

Step 0, context (yours; a subagent can't talk to me). Before any research, ask me what the request doesn't already answer, a few questions at a time.
1. **Project and plan id.** Ask whether this belongs to an existing subfolder of ~/Developing or is a new project. Propose a project name (short, lowercase, hyphens) and a plan id (two or three words, such as `first-version`), and wait for my yes or my own names. For a new project, create it with `python3 ~/Developing/scripts/new_project.py <name> "<one-line description>"`; it makes the folder, its files and a git repo with dev and uat.
2. Create the planning folder. Write my request verbatim to request.md. Make sure the project's `.gitignore` has the line `docs/planning/*/spikes/`. From here on, write each of my answers in my words to 00-context.md as I give it; every later step reads that file.
3. **Outcome.** What the finished thing must show, to whom, and by when. What is explicitly out of scope.
4. **Deployment.** Whether it runs only on this machine or must be reachable elsewhere; if elsewhere: which service and account, which environment (one for a proof of concept, or dev, uat and production), the URL or domain if there is one, and who says go for each deploy. Nothing is deployed without my go.
5. **Resources.** External services and APIs it may use; which credentials already exist and where they live (the name of the env var or file, never the value); spending limits for APIs and hosting; the data it needs and where it comes from; which models it may call.
6. **Seams.** Anything it must cross that only shows in the real environment: sign-in, network and firewall rules, DNS and TLS, secrets, operating-system permissions, hardware, other people's APIs.
7. **Constraints.** Stack choices beyond the workspace defaults, privacy and data handling, things that must not be touched, and whether it changes LLM or agent behaviour (then it needs eval cases).
When I say the context is complete, record step 0 in progress.md and go to step 1.

For steps 1, 2, 3, 4 and 6:
1. Call the planner subagent with the project, the planning folder's absolute path and the step number, and wait for it to finish.
2. Give me the path of the file it wrote and ask me to read it in full; I review the file, not your summary. Add at most 5 lines on what to look at.
3. Append a line to progress.md: step number, file name, time, one-line summary.
4. Ask me whether to go on, change something in this step, or stop. Go to the next step only when I say so.

Committing the plan. The planning files are part of the project. Commit them twice, each time on the branch `feature/<plan-id>-plan` off an up-to-date dev, with only the planning folder staged (`git add docs/planning/<plan-id>`; the spikes are git-ignored), then merge the branch into dev the way loop.md section 4b says (a PR, or a local `git merge --no-ff` when the repo has no GitHub remote, saying so):
- after step 4, before any risk task is built, with the subject `X0: Planning documents of <plan-id>, steps 0 to 4`;
- after step 6, with the subject `X0: Planning documents of <plan-id>, the solution and the PRD`.
These commits need no model review: I read every file at its step. Never commit to dev directly.

Risk tasks, between step 4 and step 5 (yours). Step 4 ends with the risk tasks: the seams still risky enough to build for real before the solution is fixed, in build order. If it lists none, write that in 04-risk-tasks.md, ask me "risks retired?", and go to step 5 on my yes. Otherwise, for each risk task in order:
1. Build it as a task of its own through the build loop in .claude/workflow/loop.md, on its own branch, with every gate. Its first unit is the seam's smoke check with fixed assertions, seen to fail and then made to pass. No code skips the gates because it was written during planning.
2. Merge it into dev. If 00-context.md names a target environment, ask for my go, deploy there, and run the seam's smoke check against it. Logs and transcripts are the evidence; the fixed assertions decide pass or fail.
3. Append to 04-risk-tasks.md: the seam, the branch and merge commit, the smoke check's command and result, and where the evidence is.
4. A seam that fails: show me the evidence and decide with it. A fix goes back to the same task. A pivot is my decision; on my yes, go back to step 2 with the evidence.
When every seam passes, ask me "risks retired?". Go to step 5 only on my yes, and record it in progress.md. 04-risk-tasks.md goes into the second commit of the plan.

For step 5, refine the solution with me (a subagent can't talk to me, so this part is yours):
1. Call the planner subagent, as above, for step 5 "draft". It writes 05-solution-draft.md.
2. Work through the draft with me here, one question at a time: the solution architecture, the software architecture (load the architecture skill for contracts and module boundaries) and the process flow diagram for each user story.
3. After each of my answers, append the decision in my words to 05-decisions.md, so a crash loses nothing. Apart from request.md, 00-context.md, 04-risk-tasks.md and progress.md, that log is the only file you write; the planner writes every step file itself.
4. When I say the refinement is done, call the planner subagent for step 5 "finalize". It writes 05-solution.md. Point me to it to read in full, with at most 5 lines on what to look at, then record step 5 in progress.md.

After step 6, point me to 06-prd.md to read in full, commit the plan the second time, then ask whether to start `/build <project>/<plan-id>`.
