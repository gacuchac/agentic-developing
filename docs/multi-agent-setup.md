# Multi-model agent workflow for Claude Code in VS Code

> **Historical spec.** This describes the first version of the workflow, copied into each project, with Modes A, B and C. The live rules are [CLAUDE.md](../CLAUDE.md) and [.claude/workflow/loop.md](../.claude/workflow/loop.md): the workflow lives only in this workspace root, the modes are Simple, Parallel and Sequential, commits are capped at 30 lines and reviewed one at a time, and each PR gets a full `pr` review.

## 0. How to use this document

This document is addressed to you, the Claude Code agent running in the VS Code extension. Your job is to set up the workflow described below in the current repository, then prove it works with the smoke test in section 11.

Rules for you while setting this up:

- Create the files exactly as given in section 7 and 8. The OpenAI models are GPT-6 Sol (`gpt-6-sol`) and GPT-6 Luna (`gpt-6-luna`), set in `.claude/settings.json`. If Codex rejects either model name, tell me.
- Use only Claude Code features that exist in the current official Claude Code docs. If a field, flag or behaviour below does not work as described, stop, tell me what failed, and check the docs. Do not invent syntax.
- Do not handle API keys or sign-in for me. If the Codex CLI is missing or not signed in, tell me and continue with everything else.
- Don't change any GitHub setting yourself (default branch, branch protection, rulesets, accounts). Section 9b is a checklist for me.
- Section 12 lists the parts I am least sure of. Test those explicitly during the smoke test and report the result.
- Use Python for every script.

## 1. Goal

A reusable, repo-local workflow with:

- a main **orchestrator** (Opus-class) that talks to me, classifies each feature or bug, calls the decomposers and cross-checks their plans, merges the results and makes sure everything gets done,
- **workflow orchestrators** (Opus-class) that each build one checked plan in their own git worktree, through a fixed loop,
- a **planner** subagent that takes a new product or large feature from research to a PRD in six steps; the main session calls it once per step, checks in with me after each one, and every step's output is saved to a file so the work can resume after a crash,
- an **architecture** skill the main session loads for any contract or architectural change,
- **specialist subagents**: decomposer (called only by the main orchestrator), QA, implementer (Sonnet-class when the spec is clear),
- an **OpenAI reviewer** that runs targeted review passes through the Codex CLI: GPT-6 Sol reviews plans, and GPT-6 Luna (fast and cheap, but good only with a clear rubric) runs every rubric-based pass,
- a **wild-card** agent on GPT-6 Sol that proposes bold, unconventional approaches; most will be wrong, so Opus rates them and adopts one only on merit,
- **evals** for anything that touches LLM or agent behaviour: cases written with me, a simulated user that runs them, cheap code checks, and a GPT-6 Luna judge that scores each dimension separately,
- a **branch flow** from task branches to `dev`, `uat` and `main`, checked by CI, with `main` taking changes only from `uat` and only with my approval.

It must be fast enough to run live in a time-boxed build of about 90 minutes, and every step must be easy to inspect.

Why mix model families: Opus is reliable and conservative, which makes it the right orchestrator. A different model family reviewing catches different mistakes, and an OpenAI model asked for ideas produces bolder options (some excellent, some bad). Opus filters those ideas; it never applies them blindly.

## 2. Roles and models

| Role | Where it runs | Model | Can edit code |
| --- | --- | --- | --- |
| Main orchestrator | Main session; talks to me, plans, cross-checks and merges | Opus (pick it in the model picker) | Only in Mode C, through subagents; resolves merge conflicts itself |
| `workflow-orchestrator` | Subagent, own git worktree; builds one checked plan | `opus` | Through its subagents |
| `decomposer` | Subagent, called only by the main orchestrator, up to 3 at a time | `opus` | No (writes the plan file only) |
| `qa` | Subagent | `sonnet` | Tests only |
| `implementer` | Subagent | `sonnet` | Source only, never tests |
| `planner` | Subagent, called by the main session once per step (`/planner`) | `opus` | Throwaway spike code only, in the run folder |
| `architecture` | Skill loaded by the main session | Main session model (Opus) | Proposes first; edits only after I approve |
| `codex-reviewer` | Subagent that shells out to Codex CLI | `haiku` wrapper; GPT-6 Sol for `plan`, GPT-6 Luna for `answers-ask`, `principles` and `alternatives` | No |
| `wild-card` | Subagent that shells out to Codex CLI, used by `/codex-ideas` | `haiku` wrapper; GPT-6 Sol | No |
| Eval creation | Main session (`/eval-create`), with me | Opus | Eval cases only |
| `eval-runner` | Subagent that plays the user | `sonnet` | No; writes transcripts only |
| `eval-judge` | Subagent that shells out to Codex CLI | `haiku` wrapper; GPT-6 Luna | No |

`codex-reviewer`, `wild-card` and `eval-judge` use Haiku only as a thin, cheap wrapper: each runs a script and returns Codex's answer word for word. The actual work is done by the OpenAI model.

## 3. Routing: the three modes

The main orchestrator classifies every task before doing anything else and states the classification in one line.

**Mode A: Simple.** All of these are true:
- touches one or at most two files,
- needs no architectural change and no change to any function's input or output contract,
- is easy to test (a few small tests at most),
- doesn't change LLM or agent behaviour (prompts, tool definitions, model calls), since that needs evals.

Route: on the task's own branch off `dev` (section 4b): `implementer` → `qa` runs tests → `codex-reviewer` passes `answers-ask` and `principles` → done, or one fix round → merged into `dev` by PR.

**Mode B: Complex and parallelizable.** The task can be split into pieces that can be built at the same time: no piece changes a function or contract that another piece changes or relies on. Pieces that touch the same file in different functions count as independent. Clearly defined and easy to evaluate, even if it touches many files.

Route: the build loop in section 4. The main orchestrator splits the work into tasks, calls a decomposer for each one that's ready and cross-checks the plans. It then hands each checked plan to its own `workflow-orchestrator`, which builds it in its own git worktree, with at most 3 subagents running at once. When they finish, the main orchestrator merges each branch into `dev` by PR, resolving any conflicts itself, and runs a final `answers-ask` review over the merged result.

**Mode C: Complex, not parallelizable, or sensitive.** Any of these is true:
- the pieces have dependencies on each other,
- it needs an architectural or contract change,
- I said it is sensitive or I want to watch it.

Route: the same build loop, but after planning, the main session builds each task itself, one at a time and step by step, on the task's branch in the main checkout, calling each subagent directly. This keeps every subagent visible in the main conversation and in the VS Code agent map, so I can open each trace.

**Overrides.** If my request starts with `simple:`, `parallel:` or `sequential:`, use Mode A, B or C respectively without classifying.

**Escalation.** No subagent ever changes the architecture on its own, whether the solution architecture or the software architecture; a change to any function's input or output contract counts. A subagent that finds it needs one follows the architecture stop rule in section 4: it writes the proposed change to a file in the run folder and stops. The main session then brings the change to me before anything goes on. Once I've decided, that work moves to Mode C, where the main session loads the `architecture` skill. In Mode B, a workflow orchestrator that hits this stops and reports back, because the change may affect the other parallel tasks.

**Before routing.** For a new product or a large feature, I may run `/planner` first. Its PRD lists the big architectural tasks with their dependencies; `/build` then builds them with the loop in section 4, decomposing each task only once the tasks it depends on are merged.

## 4. The build loop (Mode B and Mode C)

There are two kinds of orchestrator. The **main orchestrator** is the main session: it talks to me, plans every task, cross-checks the plans and merges the results. A **workflow orchestrator** owns one git worktree and builds one checked plan there. In Mode C the main session does that building itself.

Every task gets a run folder `.claude/runs/<task-id>/` (git-ignored) holding `ask.md` (the request, verbatim), `plan.md`, its eval cases until they're built, and review outputs. A feature that splits into several tasks, or a PRD built with `/build`, also gets a build board, `build-board.md`, in its own run folder: one row per task with its task-id, title, the tasks it depends on, its status (waiting, ready, planning, planned, building, merging, merged or blocked), its branch and a note. The main orchestrator updates the board after every change of status, so a crashed session can resume from it.

**Concurrency.** At most 3 subagents run at the same time, of any kind. The main orchestrator never has more than 3 running at once, whether decomposers, workflow orchestrators or any other. Each workflow orchestrator runs its own subagents one at a time.

### Plan (main orchestrator, for every task)

1. **Pick ready tasks (just-in-time decomposition).** A task is ready when every task it depends on is merged into dev. Decompose only ready tasks, so a contract or architecture change upstream never forces a plan to be redone.
2. **Decompose.** For each ready task, the main orchestrator calls `decomposer`, up to 3 at a time. Each reads the ask and the code on dev and writes `plan.md` (format in section 7.4): user stories, subtasks with done lines, the files and functions it will touch, the contracts it touches, how it expects to solve the task, an Evals flag and open questions. Workflow orchestrators never decompose; keeping every decomposition in the main session is what lets the plans be cross-checked.
3. **Read each plan.** If its Contracts section lists any changed function, or an `architecture-change-*.md` file exists, apply the architecture stop rule below. If Open questions holds anything that blocks the plan, bring the questions to me.
4. **Cross-check.** The main orchestrator compares the new plans with each other and with the plans of tasks still building, and writes what it found to `cross-check.md` in the board's run folder. A clash is two plans changing the same function or contract, one plan relying on a function or contract that another changes, or two plans building the same thing. Touching the same file in different functions is not a clash. It sends each clash back to the decomposers concerned with full context (their own plan, the other plan and the clash), then checks again. After 3 rounds with a clash left, it builds one of the two tasks now and holds the other back, to be decomposed again once the first is merged; if neither can wait, it brings the clash to me.
5. **Review each plan.** `codex-reviewer` runs pass `plan` (GPT-6 Sol). If the verdict is `CHANGES`, send the findings back to `decomposer` once, and cross-check that plan again if it changed.
6. **Create evals (only if the Evals flag is yes).** The main session writes the eval cases with me, using `/eval-create` (section 5b). They stay in the task's run folder until the task is built.

Each checked plan then goes to the build. In Mode B it goes to a new `workflow-orchestrator` in its own worktree, with the full text of `ask.md`, `plan.md`, any approved `architecture.md` and the eval cases. In Mode C the main session builds it, one task at a time.

### Build (a workflow orchestrator in Mode B, the main session in Mode C)

1. **Set up.** Work on the task's own branch, starting from dev's tip (section 4b). Write the plan files to the run folder and the eval cases to `evals/cases/`.
2. **Write tests.** `qa` writes tests for the plan under `tests/`, each named after the user story it checks, and confirms they fail for the right reason.
3. **Implement.** `implementer` builds each subtask. It never edits tests or evals.
4. **Run tests.** `qa` runs the new and affected tests first and reports pass/fail with the failing output. Once they pass, it runs the full suite once before the final review.
5. **Run evals (only if the Evals flag is yes).** For each case: `eval-runner` plays the user, `scripts/eval_checks.py` runs the code checks, and `eval-judge` scores the run (section 5b).
6. **Final review.** `codex-reviewer` runs passes `answers-ask`, `principles`, then `alternatives` (all GPT-6 Luna, each with its rubric), with the launch hash as the base.
7. **Decide.**
   - all tests pass, every eval case passes, and `answers-ask` is `PASS` → done: commit on the task's branch (`alternatives` findings are reported, not acted on, unless one is clearly better and cheap),
   - tests fail, an eval case fails, or review finds a defect in the code → back to step 3,
   - review or evals show the plan itself was wrong, or the tests don't test the real ask → back to Plan: a workflow orchestrator stops and reports STATUS: REPLAN with the reason; the main orchestrator sends that reason to `decomposer`, then cross-checks and reviews the new plan before it's built again,
   - any subagent reports `ARCHITECTURE CHANGE`, or a review finding can only be fixed by an architecture change → follow the architecture stop rule below.

Stop after **3** rounds through step 7 and report to me with what is blocking, rather than looping further.

### Merge (main orchestrator)

For each finished task, one branch at a time, working in that task's worktree (Mode B) or the main checkout (Mode C):

1. Fetch and merge the latest dev into the branch. The main orchestrator resolves any conflict itself. If a conflict can only be resolved by changing a contract or the architecture, it applies the architecture stop rule.
2. `qa` runs the full suite on the branch.
3. Push the branch, open a PR into dev, wait for its checks and merge it (section 4b).
4. Remove the worktree, pull dev in the main checkout, and mark the task merged on the board.

When every task launched together is merged, `codex-reviewer` runs pass `answers-ask` over the merged result, against the top-level `ask.md`, with the hash they were launched from as the base. Then the board's newly ready tasks go back to Plan.

**Architecture stop rule (every subagent).** If any subagent finds it needs to change the architecture, whether the solution architecture or the software architecture (a public function's input or output contract counts), it does not make the change. It writes the proposed change to `architecture-change-<agent name>.md` in the run folder (what must change, why, what it affects, and the options it sees), stops, and reports `ARCHITECTURE CHANGE: <path to that file>`. A workflow orchestrator that receives that report, or that finds a review finding needs an architecture change, stops its loop and reports the same line to the main session. The main session then shows me the file and waits for my decision. Until I decide, it starts no new work on that task and merges nothing from Mode B.

## 4b. Branches and environments

| Branch | Environment | Takes changes from |
| --- | --- | --- |
| `main` | production | `uat` only, by PR, with my approval |
| `uat` | UAT | `dev` or `hotfix/*`, by PR |
| `dev` | dev | `feature/*`, `bugfix/*` or `hotfix/*`, by PR |

- Nothing is committed to `main`, `uat` or `dev` directly. Everything arrives by PR.
- Every task works on its own branch off an up-to-date `dev`: `feature/<task-id>` for a feature, `bugfix/<task-id>` for a bug, and `hotfix/<task-id>` only when I call it a hotfix. In Mode B, each workflow orchestrator's worktree is its task's branch.
- Before any work starts, the main checkout must be on `dev`, clean and up to date: `git switch dev`, `git status --porcelain` printing nothing, then `git pull --ff-only`. If there are uncommitted changes, stop and ask me what to do with them; never commit them to `dev`. The launch hash is `dev`'s tip after the pull (`git rev-parse HEAD`).
- Use merge commits (`gh pr merge --merge`), never squash or rebase merges, so the histories of `dev`, `uat` and `main` stay compatible.
- Agents may, on their own: merge a task's PR into `dev` once its checks pass (`gh pr create --base dev --fill`, `gh pr checks --watch`, `gh pr merge --merge`); promote `dev` to `uat` with a PR from `dev` into `uat`, merged once its checks pass; and send a hotfix to `uat` with a PR from its `hotfix/` branch, as well as to `dev`.
- When I ask for a release, open a PR from `uat` into `main` and stop. Never approve or merge a PR into `main`; I do that.
- Merging into `dev` or `uat` may deploy that environment; that's allowed. Nothing reaches production without my approval.
- If the repo has no GitHub remote (as in the smoke test), merge into `dev` locally with `git merge --no-ff <branch>` instead of a PR, and say so. That's the only exception.
- `.github/workflows/branch-order.yml` (section 7.26) checks every PR's source branch against the table above. Branch protection (section 9b) makes PRs and my approval on `main` mandatory; I apply it by hand.

## 5. Review passes

Each pass is narrow on purpose. Each lives in `.claude/review-passes/<pass>.md` and is run by `scripts/codex_review.py`, which picks the model by pass.

**GPT-6 Sol, open-ended:**

- **plan**: does the plan, if executed, deliver the ask? Missing subtasks, wrong order, hidden contract changes, untestable steps, done lines that don't match their stories.
- **ideas** (via the `wild-card` agent and `/codex-ideas`): bold, unconventional approaches to the ask. Most will be wrong. Opus rates each one and adopts one only if it clearly beats the current plan, and never without my yes.

**GPT-6 Luna, with a fixed rubric.** Luna is fast and cheap but reliable only with a clear rubric, so each pass answers every criterion with PASS, FAIL or N/A plus evidence (file and line). The verdict is `CHANGES` if any criterion is FAIL.

- **answers-ask**:
  - A1. Every user story in `plan.md` is delivered by code you can name (file and function).
  - A2. Every subtask's done line is met.
  - A3. For a bug: the reported failing case now behaves correctly.
  - A4. No test gaming: no hard-coded expected outputs and no special-casing of test inputs.
  - A5. No test was deleted, skipped or loosened compared with the base.
  - A6. Nothing outside the subtasks was changed.
- **principles**:
  - P1. Each new or changed function has one purpose.
  - P2. Each public function has typed inputs and outputs and a docstring that states its contract.
  - P3. No public function's signature or output shape changed, unless an approved `architecture.md` covers it.
  - P4. No function relies on hidden or global mutable state.
  - P5. Functions use other functions only through their contracts, not their internals.
  - P6. Each module keeps one clear responsibility.
- **alternatives**:
  - L1. Is there an approach with clearly less code or fewer moving parts that meets the same stories?
  - L2. Is there a clearly more robust approach (errors, edge cases) at similar cost?
  - L3. Does the change rebuild something the codebase or the standard library already provides?
  For each FAIL: the alternative in one sentence and its trade-off. `VERDICT: PASS` when none is clearly better.

Every review pass except **ideas** answers with a first line of exactly `VERDICT: PASS` or `VERDICT: CHANGES`, followed by its findings.

## 5b. Evals

Evals run for any task whose plan has the Evals flag set, meaning it changes LLM or agent behaviour: prompts, tool definitions, model calls or the agent loop. `qa` still covers unit and regression tests of the code and of the eval harness; it doesn't write, run or judge evals.

**(a) Create, with me.** `/eval-create <task-id>` runs in the main session on Opus. It drafts one case at a time and goes through it with me before saving it to the task's run folder as `evals/<case-id>.yaml`. Whoever builds the task copies the cases to `evals/cases/` on the task's branch and commits them there, so nothing is committed to `dev` directly. Each case has a persona, a goal, a stop condition, a turn cap, and branching logic for how the simulated user reacts to the agent's replies, plus budgets and pass thresholds. Example:

```yaml
id: refund-duplicate-charge
story: US-2
persona: Busy customer, short messages, irritated after a double charge.
goal: Get a refund for the duplicate charge on their last order.
opening_message: "I got charged twice. Fix it."
branches:
  - if: the agent asks for the order number
    then: give it, A-1043
  - if: the agent offers store credit instead of a refund
    then: refuse and repeat that they want the money back
stop_condition: The agent confirms a refund for the duplicate charge, or the user gives up.
max_turns: 8
budgets: {max_tool_calls: 6, max_total_tokens: 20000, max_seconds: 60}
thresholds: {tool_use: 4, groundedness: 4, answers_question: 4, completeness: 4}
```

**(b) Run.** `eval-runner` (Sonnet) role-plays the user against the agent under test, through the project's eval harness. It sees only what a real user sees: the case and the agent's visible replies, never the code or the trace. It saves the transcript to `evals/runs/<run-id>/<case-id>/transcript.md`; the harness saves the full trace next to it as `trace.jsonl`.

Harness contract (project code in `harness/`, built by the implementer and tested by `qa` like any other code; the decomposer adds it as a subtask if it doesn't exist yet):
`python3 -m harness --case <case-id> --run <run-id> --message "<text>"` sends one user message to the agent under test in that case's session, prints only the agent's visible reply, and appends to `evals/runs/<run-id>/<case-id>/trace.jsonl` one JSON event per line: `{"type": "model_call", "input_tokens": n, "output_tokens": n, "ts": seconds}`, `{"type": "tool_call", "tool": name, "args": {...}, "output": ..., "ts": seconds}`, and `{"type": "turn", "role": "user" or "agent", "text": ..., "ts": seconds}`.

**(c) Judge.** Two parts, each reported per dimension, never blended into one number:
- **Code checks** (cheap, no model): `python3 scripts/eval_checks.py <run dir> <case file>` checks tool-call count, redundant calls (the same tool with the same arguments more than once), total tokens and wall time against the case's budgets, and writes `checks.json`.
- **Judge** (`eval-judge`, GPT-6 Luna): reads the case, the transcript, the full trace and `checks.json` against the rubric in `.claude/review-passes/judge.md`, and scores 1 to 5, with evidence, four separate dimensions: whether each tool call makes sense (`tool_use`), groundedness against tool outputs (`groundedness`), whether it answers the question (`answers_question`), and completeness (`completeness`). It writes `scores.json`.

A case passes only when every code check passes and every dimension meets the case's threshold.

**Calibration.** `/eval-calibrate <run-id>`: I grade a few transcripts by hand on the same four dimensions, without seeing the judge's scores. The main session compares my grades with the judge's per dimension and proposes rubric fixes where we differ by more than a point; it changes the rubric only with my yes.

**Ownership.** The implementer never edits anything under `evals/` or the judge rubric. The harness lives outside `evals/` because it's ordinary code.

## 6. Coding principles (goes into CLAUDE.md)

- Cohesive and modular: each module has one clear responsibility.
- Lean functional: prefer pure, stateless functions. Object-oriented code is fine where it fits, but methods still follow the rules below.
- One purpose per function. Internal helper functions inside a class or module are fine, as long as the behaviour is encapsulated.
- Clear input and output contracts. Each public function has typed inputs and outputs and a docstring that states the contract.
- Contracts are stable. A change or bug fix inside a function must not force any caller to change, as long as the output keeps the same shape and meaning. Fix the function so downstream code keeps working unchanged.
- Changing a contract is an architectural change. It goes through the `architecture` skill in the main session and is never handed to the implementer.
- No subagent changes the solution architecture or the software architecture itself. It writes the proposed change to a file in the run folder and stops, and the main session brings it to me before anything goes on.
- Functions don't depend on hidden state or on the internals of other functions; only on their contracts.

## 7. Files to create

Create this layout:

```
CLAUDE.md
README.md
.gitignore                      (add: .claude/runs/ and evals/runs/)
.claude/settings.json
.claude/workflow/loop.md
.claude/agents/workflow-orchestrator.md
.claude/agents/decomposer.md
.claude/agents/qa.md
.claude/agents/implementer.md
.claude/agents/codex-reviewer.md
.claude/agents/wild-card.md
.claude/agents/eval-runner.md
.claude/agents/eval-judge.md
.claude/agents/planner.md
.claude/commands/planner.md
.claude/skills/architecture/SKILL.md
.claude/commands/feature.md
.claude/commands/build.md
.claude/commands/review-pass.md
.claude/commands/codex-ideas.md
.claude/commands/eval-create.md
.claude/commands/eval-calibrate.md
.claude/review-passes/plan.md
.claude/review-passes/answers-ask.md
.claude/review-passes/alternatives.md
.claude/review-passes/principles.md
.claude/review-passes/ideas.md
.claude/review-passes/judge.md
scripts/codex_review.py
scripts/eval_checks.py
evals/cases/                    (filled by /eval-create)
scripts/hooks/post_edit.py
scripts/ci/check_branch_order.py
tests/test_check_branch_order.py
.github/workflows/branch-order.yml
```

### 7.1 `CLAUDE.md`

```markdown
# Project instructions

## Coding principles
(Copy section 6 of the setup document here, as a bullet list.)

## How work is routed
You are the main orchestrator. For every feature or bug:
1. Classify it as Mode A (simple), B (complex, parallelizable) or C (complex, sequential or sensitive) using the rules in @.claude/workflow/loop.md, and state the mode in one line.
2. Honour overrides: a request starting with `simple:`, `parallel:` or `sequential:` forces Mode A, B or C.
3. Follow the route for that mode in @.claude/workflow/loop.md.
4. Never let the implementer change a function contract. For any contract or architectural change, load the architecture skill, show me its proposal and wait for my approval before anyone edits code.
5. When any subagent reports `ARCHITECTURE CHANGE: <file>`, stop that work, show me the file, and wait for my decision before anything goes on. Start no new work on that task and merge nothing from Mode B until I decide.
6. For a new product or large feature, I may run /planner first; then build the PRD with /build.
7. You call every decomposer yourself; workflow orchestrators never decompose. Cross-check the plans before anything is built, and decompose a task only once every task it depends on is merged into dev.
8. At most 3 subagents run at the same time, of any kind. Each workflow orchestrator runs its own subagents one at a time.
9. When a plan's Evals flag is yes, write the eval cases with me using /eval-create before that task is built.
10. Never commit to main, uat or dev directly. Each task gets a feature/, bugfix/ or hotfix/ branch off a clean, up-to-date dev and comes back by PR. If the main checkout has uncommitted changes, stop and ask me. You may merge PRs into dev and promote dev or a hotfix to uat. Never approve or merge a PR into main; I do that.

## Conventions
- Python, tests with pytest under tests/.
- Per-task working files live in .claude/runs/<task-id>/ (git-ignored).
- Eval cases are written to the task's run folder, then committed to evals/cases/ on the task's branch; eval runs go in evals/runs/ (git-ignored). The implementer never edits evals/.
- Branches map to environments: dev to dev, uat to UAT, main to production. Merging into dev or uat may deploy that environment, which is allowed; nothing reaches production without my approval.
- Quick deploys outside that flow use my personal Railway and GitHub accounts. Deploy only when I ask.
```

### 7.2 `.claude/workflow/loop.md`

Put sections 3, 4, 4b, 5 and 5b of this document here, unchanged, under the heading `# Workflow`. Both the main orchestrator (via the import in CLAUDE.md) and each `workflow-orchestrator` (by reading the file) follow it.

### 7.3 `.claude/agents/workflow-orchestrator.md`

```markdown
---
name: workflow-orchestrator
description: Builds ONE checked plan in its own git worktree - tests, implementation, test runs, evals and reviews. Use only for Mode B tasks the main orchestrator has already decomposed and cross-checked.
tools: Agent, Read, Write, Grep, Glob, Bash
model: opus
isolation: worktree
color: purple
---

You own one task's build, in this worktree. Follow the Build steps in .claude/workflow/loop.md exactly. You don't decompose or re-plan; the main orchestrator does that.

You are given: the task-id, the branch name (feature/<task-id>, bugfix/<task-id> or hotfix/<task-id>), the launch hash, and the full text of ask.md, plan.md, any approved architecture.md, and any eval cases.

Setup:
- Run `pwd` and `git rev-parse --abbrev-ref HEAD` first. Record the absolute worktree path.
- Run `git merge-base --is-ancestor <launch hash> HEAD`. If it fails, your worktree doesn't start from the latest dev: stop and report STATUS: BLOCKED, stale base.
- Rename your branch: `git branch -m <branch name>`.
- Write ask.md, plan.md and architecture.md (if given) to .claude/runs/<task-id>/ exactly as given, and each eval case to evals/cases/<case-id>.yaml.
- If plan.md's Evals flag is yes and you were given no eval cases, stop and report STATUS: BLOCKED with the reason.
- Every subagent you call must be told the absolute worktree path and to work only inside it (prefix Bash commands with `cd <path> &&`).

Rules:
- Call qa, implementer, codex-reviewer, eval-runner and eval-judge as subagents, one at a time. Never call the decomposer and never edit plan.md. Never decide a contract or architectural change yourself; that belongs to the main session.
- If the plan turns out to be wrong (a review or eval shows it can't deliver the ask, or the tests can't check the real ask), stop and report STATUS: REPLAN with the reason and the evidence.
- If a subagent reports `ARCHITECTURE CHANGE: <file>`, or a review finding can only be fixed by changing the solution or software architecture, stop the loop at once. In the second case, write the proposed change to architecture-change-workflow-orchestrator.md in the run folder yourself. Report STATUS: ARCHITECTURE CHANGE with the file's absolute path.
- Stop after 3 decision rounds and report what blocks you.
- When done, commit everything on your branch, eval cases included, with a short message. Don't push, open a PR or merge; the main orchestrator does that.

Final report, in this order:
STATUS: DONE | BLOCKED | REPLAN | ARCHITECTURE CHANGE
BRANCH: <branch>   WORKTREE: <absolute path>
SUMMARY: 2 to 4 sentences.
FILES: every file the branch touched (`git diff --name-only <launch hash> HEAD`).
FUNCTIONS: every function added or changed, as <file>:<function>.
TESTS: pass/fail counts.
EVALS: per case, each code check and each dimension score, or "not flagged".
REVIEWS: the VERDICT line of each pass, and any unresolved finding.
```

### 7.4 `.claude/agents/decomposer.md`

```markdown
---
name: decomposer
description: Breaks ONE task into ordered subtasks and writes plan.md. Called only by the main orchestrator, up to three at a time, before anything is built.
tools: Read, Grep, Glob, Write
model: opus
color: blue
---

Read ask.md in the run folder you are given and the relevant code on dev. Write plan.md in that run folder and nothing else.

plan.md format:
## User stories
The stories this task delivers, each with an id (US-1, US-2, ...). Take them from the ask or the planner's PRD; if neither has any, write them from the ask and mark them as inferred.
## Approach
How you expect to solve the task, in a few sentences.
## Subtasks
1. <title> (story: US-n): files touched, function contracts touched (name, inputs, outputs), tests needed.
   Done when: one checkable line tied to that story.
## Files and functions
Every file you expect to touch, and in each, every function you'll add or change, as <file>:<function>.
## Contracts
List every public function whose signature or output shape would change.
## Parallelism
Which subtasks are independent of each other.
## Evals
Evals flag: yes or no. Yes if the task changes LLM or agent behaviour (prompts, tool definitions, model calls, the agent loop). If yes: which stories need eval cases, and whether the eval harness exists (if not, add building it as a subtask).
## Open questions
Every ambiguity you would otherwise have to guess, with the options you see. Don't guess; list it here.

Keep subtasks small enough that each is clearly specified for a Sonnet-class implementer.

If the main orchestrator sends you clashes with other plans, you get your plan, the other plans and each clash. Revise your plan so the clashes go away without changing the other tasks, and add a section "## Changes since last round" saying what you changed and why. If a clash can't go away without changing a contract, say so there instead.

Architecture stop rule: if you find you need to change the solution architecture or the software architecture (a public function's inputs or output shape counts), don't make the change. Write the proposed change to architecture-change-<your name>.md in the run folder: what must change, why, what it affects, and the options you see. Then stop and report `ARCHITECTURE CHANGE: <absolute path to that file>`.
```

### 7.5 `.claude/agents/qa.md`

```markdown
---
name: qa
description: Writes tests from a plan, or runs the test suite and reports results. Say "write tests" or "run tests".
tools: Read, Grep, Glob, Write, Edit, Bash
model: sonnet
color: green
---

Write tests mode:
- Write pytest tests under tests/ that check the behaviour in plan.md and the original ask, including edge cases.
- Name each test after the user story it checks, as test_<story id>_<behaviour> (for example test_us2_refunds_duplicate_charge), so a failure says which story broke.
- Test behaviour through public contracts, not internals.
- Run them and confirm they fail because the feature is missing, not because of a test bug.
- Never edit source files.

Run tests mode:
- During the loop, run the new and affected tests first: `python3 -m pytest -q <test files>`.
- When they pass, or when asked for the full suite (before the final review, and after a Mode B merge), run `python3 -m pytest -q`.
- Report pass/fail counts and the full output of each failure. Do not fix anything.

You cover unit and regression tests of the code and of the eval harness. You don't write, run or judge evals.

Architecture stop rule: if you find you need to change the solution architecture or the software architecture (a public function's inputs or output shape counts), don't make the change. Write the proposed change to architecture-change-<your name>.md in the run folder: what must change, why, what it affects, and the options you see. Then stop and report `ARCHITECTURE CHANGE: <absolute path to that file>`. This includes tests that could only be written against a changed contract.
```

### 7.6 `.claude/agents/implementer.md`

```markdown
---
name: implementer
description: Implements clearly specified subtasks from plan.md, or a Mode A simple task. Use when the spec is clear and no contract changes are needed.
tools: Read, Grep, Glob, Edit, Write, Bash
model: sonnet
color: orange
---

Follow the coding principles in CLAUDE.md.
- Implement only the subtasks you were given.
- Never edit files under tests/. If a test looks wrong, say so in your report.
- Never edit anything under evals/ or the judge rubric.
- Architecture stop rule: if you find you need to change the solution architecture or the software architecture (a public function's inputs or output shape counts), don't make the change. Write the proposed change to architecture-change-<your name>.md in the run folder: what must change, why, what it affects, and the options you see. Then stop and report `ARCHITECTURE CHANGE: <absolute path to that file>`.
- Run the relevant tests before reporting.
Report: files changed, what each change does, test result.
```

### 7.7 `.claude/skills/architecture/SKILL.md`

A skill, not a subagent, so it runs in the main session where it can talk to me directly and wait for my approval.

```markdown
---
name: architecture
description: Use whenever a function's input or output contract must change, a task needs an architectural change, or a plan needs its solution or software architecture worked out. Proposes first and edits nothing until the user approves.
---

1. Write a proposal to the run folder as architecture.md: the old and new contract (or the proposed architecture), every caller or dependent found with Grep, the migration order, the risks, and how the tests must change.
2. Show me the proposal and stop. Do not edit code until I approve it in this conversation.
3. After I approve: apply the change and update every caller. You may hand clearly specified caller updates to the implementer subagent. Then have qa run the full suite and codex-reviewer run passes answers-ask and principles.
```

Leave `disable-model-invocation` off so the main session loads it on its own when a contract change comes up; I can also run it as `/architecture`.

### 7.8 `.claude/agents/codex-reviewer.md`

```markdown
---
name: codex-reviewer
description: Runs one targeted review pass through the Codex CLI: GPT-6 Sol for plan, GPT-6 Luna for answers-ask, alternatives and principles.
tools: Bash, Read
model: haiku
color: cyan
---

You are a thin wrapper. Do not review the code yourself and do not edit anything.
Run exactly:
python3 scripts/codex_review.py <pass> --ask-file <run folder>/ask.md [--plan-file <run folder>/plan.md] [--base <ref>]
from the directory you were told to work in. Save the output to <run folder>/review-<pass>.md and return it word for word.
If the script fails, return its error text word for word.
```

### 7.9 `.claude/commands/feature.md`

```markdown
---
description: Classify a feature or bug and run it through the right workflow mode
argument-hint: [simple:|parallel:|sequential:] <feature or bug description>
---

Task: $ARGUMENTS

Follow the routing rules in CLAUDE.md and .claude/workflow/loop.md.
1. Give the task a short task-id and create .claude/runs/<task-id>/ask.md with the task verbatim.
2. State the mode in one line, with the reason.
3. Check that the main checkout is on dev, clean and up to date (section 4b). If it isn't clean, stop and ask me.
4. Mode A: create feature/<task-id> (bugfix/<task-id> for a bug) off dev, run the Mode A route, then merge it into dev by PR.
5. Mode B or C: split the task into tasks with their dependencies (one task if it can't be split), write them to .claude/runs/<task-id>/build-board.md, and run the build loop: Plan, then Build (workflow orchestrators in Mode B, this session in Mode C), then Merge.
6. Finish with a short summary: what was built, tests, eval results, review verdicts, PRs merged, anything left for me.
```

### 7.10 `.claude/commands/review-pass.md`

```markdown
---
description: Run one Codex review pass on the current changes
argument-hint: <plan|answers-ask|alternatives|principles> <task-id>
disable-model-invocation: true
---

Use the codex-reviewer subagent to run pass $0 for .claude/runs/$1/. Show me its output word for word, then give your own one-line assessment of whether you agree.
```

### 7.11 `.claude/commands/codex-ideas.md`

I chose to keep the wild card as its own agent and have `/codex-ideas` call it, so the command stays the one place I ask for bold ideas and Opus does the rating.

```markdown
---
description: Get bold, unconventional approaches from the wild-card agent (GPT-6 Sol), then rate them on merit
argument-hint: <task-id>
disable-model-invocation: true
---

Use the wild-card subagent for .claude/runs/$0/. Show me its ideas, then rate each one: worth trying, maybe, or reject, with one reason each. Expect most to be wrong. Recommend one only if it clearly beats the current plan, and don't apply any of them unless I say so.
```

### 7.12 Review pass prompts

Write each file from section 5 as follows.

- `plan.md` (GPT-6 Sol): "You are a plan reviewer. Be specific and brief. Your first line must be exactly `VERDICT: PASS` or `VERDICT: CHANGES`. Then list numbered findings, each with the subtask and a one-sentence reason." Then the scope of **plan** from section 5.
- `answers-ask.md`, `principles.md`, `alternatives.md` (GPT-6 Luna): "You are a code reviewer working from a fixed rubric. Answer every criterion below, in order, as `<id>: PASS | FAIL | N/A — <evidence: file:line and one sentence>`. Don't add criteria and don't skip any. Your first line must be exactly `VERDICT: CHANGES` if any criterion is FAIL, otherwise `VERDICT: PASS`." Then that pass's criteria from section 5, word for word.
- `ideas.md` (GPT-6 Sol): "Propose up to five bold, unconventional approaches to the ask. Don't play it safe. For each: the idea in two sentences, why it could be much better than the obvious approach, and the main risk. No verdict line."
- `judge.md` (GPT-6 Luna), word for word:

```
You are judging one run of an AI agent against an eval case. You get the case (persona, goal, stop condition, thresholds), the transcript the user saw, the full trace (every model call and tool call, with arguments and outputs) and the code checks.

Score each dimension separately from 1 to 5 using the anchors. Never combine them into one score. Score from the trace and transcript only; the code checks are reported separately.

1. tool_use: does each tool call make sense given what the agent knew at that point?
   5 = every call needed and well chosen. 3 = some calls unneeded or poorly chosen, none harmful. 1 = calls mostly unneeded, wrong or harmful.
2. groundedness: is every factual claim in the agent's replies supported by a tool output in the trace?
   5 = all claims supported. 3 = minor claims unsupported. 1 = key claims unsupported or contradicted by tool outputs.
3. answers_question: does the agent meet the user's goal from the case?
   5 = fully met. 3 = partly met, or met only after the user had to push. 1 = not met.
4. completeness: is anything the goal needs missing from the agent's answers?
   5 = nothing missing. 3 = minor gaps. 1 = major gaps.

For each dimension give the score and the evidence: quote the reply or name the trace event.

Output only this JSON:
{"case": "<case-id>", "tool_use": {"score": 0, "evidence": ""}, "groundedness": {"score": 0, "evidence": ""}, "answers_question": {"score": 0, "evidence": ""}, "completeness": {"score": 0, "evidence": ""}}
```

### 7.13 `scripts/codex_review.py`

```python
#!/usr/bin/env python3
"""Run one targeted Codex review pass and print Codex's final message."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

PASSES_DIR = Path(".claude/review-passes")
PASSES = ("plan", "answers-ask", "alternatives", "principles", "ideas", "judge")
NO_DIFF_PASSES = frozenset({"plan", "ideas", "judge"})
SOL_PASSES = frozenset({"plan", "ideas"})  # every other pass runs on Luna


def git(*args: str) -> str:
    """Run a git command and return stdout."""
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout


def collect_changes(base: str | None) -> str:
    """Diff of tracked changes against base (default HEAD) plus the content of new untracked files."""
    tracked = git("diff", base or "HEAD")
    untracked = git("ls-files", "--others", "--exclude-standard").splitlines()
    new_files = (f"\n### New file: {p}\n{Path(p).read_text(errors='replace')}" for p in untracked)
    return tracked + "".join(new_files)


def read_optional(path: str | None) -> str:
    """Return a file's text, or an empty string when no path or no file."""
    return Path(path).read_text() if path and Path(path).exists() else ""


def build_prompt(pass_name: str, ask: str, plan: str, principles: str, changes: str, extra: str) -> str:
    """Assemble the prompt from the pass instructions and whatever context is present."""
    sections = (
        (PASSES_DIR / f"{pass_name}.md").read_text(),
        f"## Original ask\n{ask}" if ask else "",
        f"## Plan\n{plan}" if plan else "",
        f"## Project principles (CLAUDE.md)\n{principles}" if principles else "",
        f"## Changes under review\n{changes}" if changes else "",
        extra,
    )
    return "\n\n".join(s for s in sections if s)


def context_files(paths: list[str]) -> str:
    """Each extra context file as its own section, headed by its path."""
    return "\n\n".join(f"## {p}\n{read_optional(p)}" for p in paths)


def resolve_model(pass_name: str, override: str | None) -> str:
    """Pick the model: --model, else CODEX_SOL_MODEL for plan and ideas, else CODEX_LUNA_MODEL."""
    env_key = "CODEX_SOL_MODEL" if pass_name in SOL_PASSES else "CODEX_LUNA_MODEL"
    model = override or os.environ.get(env_key, "")
    if not model or model.startswith("["):
        sys.exit(f"Set {env_key} under env in .claude/settings.json to an OpenAI model name.")
    return model


def run_codex(prompt: str, model: str) -> tuple[int, str]:
    """Run codex exec read-only with the prompt on stdin; return exit code and final message."""
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "last_message.md"
        result = subprocess.run(
            ["codex", "exec", "--model", model, "--sandbox", "read-only",
             "--output-last-message", str(out), "-"],
            input=prompt, text=True, capture_output=True,
        )
        message = out.read_text() if out.exists() else result.stderr
        return result.returncode, message


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pass_name", choices=PASSES)
    parser.add_argument("--ask-file")
    parser.add_argument("--plan-file")
    parser.add_argument("--base", help="git ref to diff against (default: HEAD)")
    parser.add_argument("--model", help="override the OpenAI model for this run")
    parser.add_argument("--context-file", action="append", default=[], help="extra file to include; repeatable")
    args = parser.parse_args()

    changes = "" if args.pass_name in NO_DIFF_PASSES else collect_changes(args.base)
    principles = read_optional("CLAUDE.md") if args.pass_name == "principles" else ""
    prompt = build_prompt(
        args.pass_name, read_optional(args.ask_file), read_optional(args.plan_file), principles, changes,
        context_files(args.context_file),
    )
    code, message = run_codex(prompt, resolve_model(args.pass_name, args.model))
    print(message)
    return code


if __name__ == "__main__":
    sys.exit(main())
```

### 7.14 `scripts/hooks/post_edit.py`

```python
#!/usr/bin/env python3
"""PostToolUse hook: format and lint a Python file Claude just edited; exit 2 shows problems to Claude."""
import json
import shutil
import subprocess
import sys


def edited_path(event: dict) -> str:
    """Path of the edited file from the hook's JSON input."""
    return event.get("tool_input", {}).get("file_path", "")


def lint(path: str) -> subprocess.CompletedProcess:
    """Format the file, then lint it."""
    subprocess.run(["ruff", "format", path], capture_output=True)
    return subprocess.run(["ruff", "check", path], capture_output=True, text=True)


def main() -> int:
    path = edited_path(json.load(sys.stdin))
    if not path.endswith(".py") or shutil.which("ruff") is None:
        return 0
    result = lint(path)
    if result.returncode == 0:
        return 0
    print(result.stdout or result.stderr, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
```

### 7.15 `.claude/agents/planner.md`

The planner does one step per call. It never runs two steps in a row, because I check in after every step.

```markdown
---
name: planner
description: Runs ONE step of the six-step planning process and saves that step's output to a file. Called by the main session with a task-id and a step number.
tools: Read, Write, Edit, Grep, Glob, Bash, WebSearch, WebFetch
model: opus
color: yellow
---

You are given a task-id and a step number. Your folder is .claude/runs/<task-id>/planner/.

Drafting the architecture in step 5 and writing it into the PRD in step 6 is your job. Changing an architecture that's already agreed (in 05-solution.md or in the codebase) is not. If a step needs that, don't make the change: write the proposed change to architecture-change-planner.md in your folder (what must change, why, what it affects, and the options you see), stop, and report `ARCHITECTURE CHANGE: <absolute path to that file>`.

Read request.md and every earlier step's file in that folder first. Do only the step you were given, write its file, and return a summary of at most 10 lines plus the file name. Do not start the next step.

Step 1: research and user stories → 01-research-and-stories.md
Research the existing code, the docs and the web. Write user stories that set the scope, and list what is out of scope.

Step 2: alternatives → 02-alternatives.md
Come up with at least three alternatives. For each: the approach, its assumptions, and a falsifiable claim for every assumption (something a test, measurement or small piece of code could prove wrong), with how you'll test it.

Step 3: test the claims → 03-claim-tests.md
Test those claims with real code, data and tests. Put throwaway code in .claude/runs/<task-id>/planner/spikes/. For each claim record: held or falsified, the evidence, and the command to rerun it.

Step 4: new alternative → 04-new-alternative.md
Build a new alternative from whatever was falsified: keep what held, replace what failed, and state its own assumptions and claims.

Step 5 has two calls:
- "draft" → 05-solution-draft.md: draft the solution architecture, the software architecture, and a process flow diagram for each user story (Mermaid flowcharts). End with the open questions the user needs to decide.
- "finalize" → 05-solution.md: rewrite the draft with every decision in 05-decisions.md applied. Those decisions are the user's; don't override them. List anything still undecided at the end.

Step 6: PRD → 06-prd.md
Write the PRD from 05-solution.md covering the problem, the solution, the architecture, the user stories, how each story maps onto the architecture, and the big architectural tasks with their dependencies.
```

### 7.16 `.claude/commands/planner.md`

The main session drives the planner, one step at a time, and keeps `progress.md` so a crashed session can pick up where it stopped.

```markdown
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
```

### 7.17 `.claude/agents/wild-card.md`

```markdown
---
name: wild-card
description: Gets bold, unconventional approaches to a task from GPT-6 Sol through the Codex CLI. Most will be wrong; the main session rates them on merit.
tools: Bash, Read
model: haiku
color: red
---

You are a thin wrapper. Don't come up with ideas yourself and don't edit anything.
Run exactly:
python3 scripts/codex_review.py ideas --ask-file <run folder>/ask.md [--plan-file <run folder>/plan.md]
(omit --plan-file if plan.md doesn't exist). Return the output word for word. If the script fails, return its error text word for word.
```

### 7.18 `.claude/agents/eval-runner.md`

```markdown
---
name: eval-runner
description: Plays the simulated user for one eval case against the agent under test, through the eval harness. Sees only what a real user would see.
tools: Bash, Read, Write
model: sonnet
color: pink
---

You are given a case file (evals/cases/<case-id>.yaml) and a run-id.
- Read only the case file. Don't read the code, the trace, other cases, or anything else under evals/runs/.
- Play the persona. Send the opening message, then each next message, with:
  python3 -m harness --case <case-id> --run <run-id> --message "<your message>"
  It prints only the agent's visible reply. That's all you know about the agent.
- React to each reply as the case's branches say. Where no branch fits, react the way the persona would, in line with the goal.
- Stop when the stop condition is met or after max_turns of your messages, whichever comes first.
- Write the transcript to evals/runs/<run-id>/<case-id>/transcript.md, each turn starting "User:" or "Agent:", ending with "ENDED: stop condition met" or "ENDED: turn cap reached".
- Report the ENDED line and the number of turns. Don't judge the agent.
```

### 7.19 `.claude/agents/eval-judge.md`

```markdown
---
name: eval-judge
description: Judges one eval run with GPT-6 Luna against the judge rubric, through the Codex CLI. Use after scripts/eval_checks.py has run.
tools: Bash, Read
model: haiku
color: cyan
---

You are a thin wrapper. Don't judge the run yourself and don't edit anything.
Run exactly:
python3 scripts/codex_review.py judge --context-file evals/cases/<case-id>.yaml --context-file <run dir>/transcript.md --context-file <run dir>/trace.jsonl --context-file <run dir>/checks.json > <run dir>/scores.json
Then return the contents of <run dir>/scores.json word for word. If the script fails, return its error text word for word.
```

### 7.20 `.claude/commands/eval-create.md`

```markdown
---
description: Write eval cases for a task with me, one case at a time
argument-hint: <task-id>
disable-model-invocation: true
---

Read .claude/runs/$0/plan.md, especially the user stories and the Evals section. Ask me how many cases each flagged story needs.
Then draft one case at a time and go through it with me before saving it:
- id, story, persona (who the user is and how they talk), goal, opening_message,
- branches: how the user reacts to the agent's replies, as "if the agent ..., then the user ...". Include at least one branch for a clarifying question from the agent and one for the agent getting something wrong.
- stop_condition and max_turns,
- budgets: max_tool_calls, max_total_tokens, max_seconds,
- thresholds: the minimum score for tool_use, groundedness, answers_question and completeness (default 4).
Save each case I approve to .claude/runs/$0/evals/<case-id>.yaml, in the format of section 5b. Don't commit anything; the cases are copied to evals/cases/ and committed on the task's branch when it's built.
```

### 7.21 `.claude/commands/eval-calibrate.md`

```markdown
---
description: Calibrate the eval judge against my own grades
argument-hint: <run-id>
disable-model-invocation: true
---

1. Pick a few transcripts from evals/runs/$0/, mixing passes and failures. Show me one at a time, with a short trace summary but without the judge's scores.
2. For each, ask me for a 1 to 5 score and a reason on tool_use, groundedness, answers_question and completeness. Save my grades to evals/calibration/$0/<case-id>.json.
3. Compare my grades with the judge's scores.json, per dimension, in a small table.
4. Where we differ by more than 1 point, propose a specific change to .claude/review-passes/judge.md. Apply it only if I say yes.
```

### 7.22 `scripts/eval_checks.py`

Needs PyYAML (`python3 -m pip install pyyaml`).

```python
#!/usr/bin/env python3
"""Code checks for one eval run: tool-call count, redundant calls, token and time budgets."""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import yaml


def load_trace(path: Path) -> list[dict]:
    """Read trace.jsonl into a list of events."""
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def tool_calls(events: list[dict]) -> list[dict]:
    """Only the tool-call events."""
    return [e for e in events if e.get("type") == "tool_call"]


def redundant_calls(calls: list[dict]) -> list[str]:
    """Tool calls repeated with identical arguments."""
    keys = Counter(f"{c.get('tool')} {json.dumps(c.get('args', {}), sort_keys=True)}" for c in calls)
    return [key for key, count in keys.items() if count > 1]


def total_tokens(events: list[dict]) -> int:
    """Input plus output tokens over all model calls."""
    return sum(
        e.get("input_tokens", 0) + e.get("output_tokens", 0) for e in events if e.get("type") == "model_call"
    )


def elapsed_seconds(events: list[dict]) -> float:
    """Wall time from the first event to the last."""
    stamps = [e["ts"] for e in events if "ts" in e]
    return max(stamps) - min(stamps) if stamps else 0.0


def check(name: str, value: float, limit: float | None) -> dict:
    """One check result; no limit means it always passes."""
    passed = limit is None or value <= limit
    return {"check": name, "value": value, "limit": limit, "result": "PASS" if passed else "FAIL"}


def run_checks(events: list[dict], budgets: dict) -> list[dict]:
    """All code checks for one run, each reported separately."""
    calls = tool_calls(events)
    repeats = redundant_calls(calls)
    return [
        check("tool_calls", len(calls), budgets.get("max_tool_calls")),
        {**check("redundant_calls", len(repeats), 0), "details": repeats},
        check("total_tokens", total_tokens(events), budgets.get("max_total_tokens")),
        check("seconds", round(elapsed_seconds(events), 1), budgets.get("max_seconds")),
    ]


def main() -> int:
    if len(sys.argv) != 3:
        sys.exit("usage: eval_checks.py <run dir> <case file>")
    run_dir, case_file = Path(sys.argv[1]), Path(sys.argv[2])
    budgets = (yaml.safe_load(case_file.read_text()) or {}).get("budgets", {})
    results = run_checks(load_trace(run_dir / "trace.jsonl"), budgets)
    output = json.dumps(results, indent=2)
    (run_dir / "checks.json").write_text(output)
    print(output)
    return 0 if all(r["result"] == "PASS" for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
```

### 7.23 `.claude/commands/build.md`

Builds a planned product or large feature from its PRD, task by task. The build board is the resume point, like the planner's `progress.md`.

```markdown
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
```

### 7.24 `scripts/ci/check_branch_order.py`

Run by the CI workflow in section 7.26. It reads the PR's branches from environment variables, never from the command line, so a branch name can't inject anything.

```python
#!/usr/bin/env python3
"""Fail a pull request whose source branch may not merge into its target branch.

Rules: main takes only uat; uat takes dev or hotfix/*; dev takes feature/*,
bugfix/* or hotfix/*. Other target branches are not checked.
Reads BASE_REF, HEAD_REF, HEAD_REPO and REPO from the environment.
"""
import os
import sys

# A rule ending in "/" is a prefix (and needs a name after it); any other rule is an exact name.
ALLOWED_SOURCES: dict[str, tuple[str, ...]] = {
    "main": ("uat",),
    "uat": ("dev", "hotfix/"),
    "dev": ("feature/", "bugfix/", "hotfix/"),
}


def matches(head: str, rule: str) -> bool:
    """Return True if the branch name head satisfies one rule."""
    if rule.endswith("/"):
        return head.startswith(rule) and len(head) > len(rule)
    return head == rule


def is_allowed(base: str, head: str, same_repo: bool) -> bool:
    """Return True if a PR from head into base follows the branch order.

    A target branch with no rule allows any source. A PR from a fork is never
    allowed into a ruled branch.
    """
    rules = ALLOWED_SOURCES.get(base)
    if rules is None:
        return True
    return same_repo and any(matches(head, rule) for rule in rules)


def main() -> int:
    """Check the PR described by the environment; return the process exit code."""
    base, head = os.environ["BASE_REF"], os.environ["HEAD_REF"]
    same_repo = os.environ.get("HEAD_REPO", "") == os.environ["REPO"]
    if is_allowed(base, head, same_repo):
        print(f"OK: {head} -> {base}")
        return 0
    if not same_repo:
        print(f"Blocked: {base} doesn't take PRs from forks.", file=sys.stderr)
        return 1
    allowed = ", ".join(rule + "*" if rule.endswith("/") else rule for rule in ALLOWED_SOURCES[base])
    print(f"Blocked: {base} only takes PRs from {allowed}, not {head}.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
```

### 7.25 `tests/test_check_branch_order.py`

```python
import importlib.util
from pathlib import Path

_path = Path(__file__).resolve().parents[1] / "scripts" / "ci" / "check_branch_order.py"
_spec = importlib.util.spec_from_file_location("check_branch_order", _path)
cbo = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cbo)


def test_main_takes_only_uat():
    assert cbo.is_allowed("main", "uat", True)
    assert not cbo.is_allowed("main", "dev", True)
    assert not cbo.is_allowed("main", "hotfix/x", True)


def test_uat_takes_dev_and_hotfixes():
    assert cbo.is_allowed("uat", "dev", True)
    assert cbo.is_allowed("uat", "hotfix/login", True)
    assert not cbo.is_allowed("uat", "feature/x", True)


def test_dev_takes_task_branches_only():
    for head in ("feature/a", "bugfix/b", "hotfix/c"):
        assert cbo.is_allowed("dev", head, True)
    for head in ("uat", "main", "feature/", "featurex", "my-branch"):
        assert not cbo.is_allowed("dev", head, True)


def test_forks_are_blocked_and_other_bases_are_open():
    assert not cbo.is_allowed("dev", "feature/a", False)
    assert cbo.is_allowed("feature/a", "anything", True)
```

### 7.26 `.github/workflows/branch-order.yml`

It runs on `pull_request_target`, so the check comes from the target branch, not from the PR: a PR can't edit the check to let itself through. It checks out only the target branch and never runs the PR's code. Because of that, the workflow and the script must be on `main`, `uat` and `dev` before branch protection is turned on.

```yaml
name: branch-order

on:
  pull_request_target:
    branches: [main, uat, dev]
    types: [opened, reopened, synchronize, edited]

permissions:
  contents: read

jobs:
  branch-order:
    runs-on: ubuntu-latest
    steps:
      - name: Check out the target branch
        uses: actions/checkout@v4
        with:
          persist-credentials: false
      - name: Check the source branch
        env:
          BASE_REF: ${{ github.base_ref }}
          HEAD_REF: ${{ github.head_ref }}
          HEAD_REPO: ${{ github.event.pull_request.head.repo.full_name }}
          REPO: ${{ github.repository }}
        run: python3 scripts/ci/check_branch_order.py
```

## 8. `.claude/settings.json`

```json
{
  "env": {
    "CODEX_SOL_MODEL": "gpt-6-sol",
    "CODEX_LUNA_MODEL": "gpt-6-luna"
  },
  "permissions": {
    "allow": [
      "Bash(python3 scripts/codex_review.py *)",
      "Bash(python3 -m pytest *)",
      "Bash(python3 -m harness *)",
      "Bash(python3 scripts/eval_checks.py *)",
      "Bash(git diff *)",
      "Bash(git status *)",
      "Bash(git log *)",
      "Bash(git fetch *)",
      "Bash(git rev-parse *)",
      "Bash(git merge-base *)",
      "Bash(git add *)",
      "Bash(git commit *)",
      "Bash(git branch -m *)",
      "Bash(git merge *)",
      "Bash(git push -u origin feature/*)",
      "Bash(git push -u origin bugfix/*)",
      "Bash(git push -u origin hotfix/*)",
      "Bash(gh pr create *)",
      "Bash(gh pr view *)",
      "Bash(gh pr checks *)",
      "Bash(gh pr merge *)"
    ]
  },
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"${CLAUDE_PROJECT_DIR}\"/scripts/hooks/post_edit.py",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

Notes:
- The hook formats and lints every Python file right after an edit, and exit code 2 shows lint problems to Claude so it fixes them immediately. It does nothing if `ruff` isn't installed.
- The git and `gh` rules let agents commit on task branches, push them and merge PRs into `dev` and `uat` without a prompt each time. Pushing to `main`, `uat` or `dev` still asks, and branch protection (section 9b) refuses a merge into `main` without my approval.
- The 3-subagent limit is in the instructions, not in a setting. Don't set `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS` to 3: if it counts nested subagents, three workflow orchestrators each waiting on a child would block one another.
- Leave the default for subagent backgrounding as is. If the main orchestrator in Mode C moves on before a subagent's result arrives, add `"CLAUDE_CODE_FORK_SUBAGENT": "0"` to `env` and start a new conversation (see section 12).

## 9. Codex: sign-in and cost

- Install the Codex CLI and sign in once, yourself, in a terminal: `codex login` to use a ChatGPT plan (usage counts against the plan's included credits), or `printenv OPENAI_API_KEY | codex login --with-api-key` to use an API key (billed at standard API rates on the OpenAI Platform account).
- Both OpenAI models run through the same sign-in: GPT-6 Sol for plan review and the wild card, GPT-6 Luna for the rubric passes and the eval judge.
- `codex exec` reuses that saved sign-in. The script runs it in a `read-only` sandbox, so the reviewer can read the repo but cannot change it.
- Each review also costs a small amount of Claude usage for the Haiku wrapper. Claude Code itself runs on the Claude subscription you sign in with in the extension; no Anthropic API key is needed.

## 9b. Branch protection (for me to apply by hand)

Create the files in sections 7.24 to 7.26, but don't change any GitHub setting yourself. This checklist is for me.

1. **Plan.** Branch protection and rulesets on a private repo need a paid GitHub plan (Pro, Team or Enterprise). On GitHub Free they work only on public repos. Without them, the check still runs and shows red, but can't block a merge.
2. **Branches.** Create `dev` and `uat` from `main` and push them. Make `dev` the default branch (Settings, General, Default branch), so new PRs and the agents' worktrees start from it.
3. **Workflow first.** Put `.github/workflows/branch-order.yml` and `scripts/ci/check_branch_order.py` on all three branches before turning protection on, and open one test PR so the `branch-order` check appears in the list of checks you can require.
4. **A second identity for the agents.** GitHub doesn't let you approve your own PR. If the agents open PRs as you, the approval rule on `main` can never be met, and turning it off leaves the rule to the agents' instructions alone. Give the agents their own GitHub account (or a GitHub App) with write access, and sign `gh` in with it yourself in the terminal VS Code uses.
5. **`main` ruleset** (Settings, Rules, Rulesets, New branch ruleset, target `main`): Restrict deletions; Block force pushes; Require a pull request before merging, with 1 required approval, Dismiss stale pull request approvals when new commits are pushed, and Require approval of the most recent reviewable push; Require status checks to pass, with `branch-order`. Leave the bypass list empty.
6. **`uat` ruleset:** Restrict deletions; Block force pushes; Require a pull request before merging, with 0 required approvals; Require status checks to pass, with `branch-order`. Empty bypass list.
7. **`dev` ruleset:** the same as `uat`. Add your test workflow's check here too if you add one later.
8. **Check it.** Open a PR from a `feature/` branch straight into `main` and confirm `branch-order` fails and the merge button stays blocked. Then close it.

## 10. README.md (how to run it)

Write a short README covering:

1. **Prerequisites:** VS Code with the Claude Code extension signed in; Python 3 with pytest and PyYAML (ruff optional); Codex CLI installed and signed in; a git repo with at least one commit.
2. **Pick Opus** for the main session in the model picker at the bottom of the prompt box.
3. **Start a task:** `/feature <description>`, or force a mode with `/feature parallel: ...`, `/feature sequential: ...`, `/feature simple: ...`. To build a planned product or large feature, `/build <task-id>` works through the PRD's tasks, decomposing each only once the tasks it depends on are merged.
4. **Watch it:** the agent count at the bottom of the prompt box opens the agent map, where each subagent's prompt, tool calls and transcript can be opened. `/tasks` opens it too. Use Mode C when you want every step in front of you.
5. **Manual passes:** `/review-pass <pass> <task-id>`, and `/codex-ideas <task-id>` for the GPT-6 Sol wild card.
6. **Planning:** `/planner <task-id> <description>` runs the six steps, one per call, and asks before each next step. Read each step's file in full before saying go on. If the session crashes, run `/planner <task-id>` again in a new conversation and it resumes from `progress.md`.
7. **Architecture:** contract or architectural changes load the architecture skill automatically; `/architecture` runs it by hand. Nothing is edited until you approve its proposal.
8. **Branches:** start on a clean, up-to-date `dev`. The agents never commit to `dev` directly: each task gets a `feature/`, `bugfix/` or `hotfix/` branch and comes back by PR. They may merge into `dev` and promote to `uat`; only you approve and merge into `main`. Keep `dev` as the GitHub default branch, because worktrees branch from the default branch.
9. **Evals:** `/eval-create <task-id>` to write cases with me, and `/eval-calibrate <run-id>` to grade a few runs by hand and tune the judge.
10. **Deploys:** quick deploys use my personal Railway and GitHub accounts, and only when I ask.
11. **CI and protection:** `.github/workflows/branch-order.yml` checks every PR's source branch. The branch protection in section 9b is applied by hand.
12. **Files:** where each agent, skill, command and pass prompt lives, so they're easy to tune.

## 11. Smoke test

Set up a tiny Python package to prove the loop end to end:

```
src/textkit/__init__.py
tests/__init__.py
pyproject.toml   (pytest config: pythonpath = ["src"])
```

Commit it on `main`, create `dev` and `uat` from it (`git branch dev && git branch uat`), and switch to `dev`. Don't add a remote; the merge falls back to local merges into `dev` (section 4b). Then run:

1. **Mode A:** `/feature simple: add textkit.slug.slugify(text: str) -> str that lowercases, trims, replaces runs of non-alphanumerics with a single hyphen, and strips leading/trailing hyphens.`
   Expect: implementer, tests run, two review passes, done.
2. **Mode B:** `/feature parallel: add textkit.stats.word_count(text: str) -> int and textkit.trim.truncate(text: str, limit: int, suffix: str = "...") -> str, in separate modules.`
   Expect: a clean, up-to-date `dev` before launch; the main orchestrator calls two decomposers, writes `cross-check.md` and reviews both plans; then two workflow orchestrators run in parallel, each in its own worktree, each confirming it started from `dev`'s tip and renaming its branch to `feature/<task-id>`; tests named after user stories; each report with FILES and FUNCTIONS lines; then a local merge of each branch into `dev`, the full suite, and a final review. At no point more than 3 subagents running.
3. **Mode C:** `/feature sequential: make slugify accept an optional separator argument, default "-".`
   Expect: classified as a contract change, the main session loads the architecture skill and shows me its proposal, nothing edited until I approve.
4. **Planner:** `/planner tk-plan a command-line tool that turns a folder of Markdown notes into a static site.` Run steps 1 and 2, stop the session, start a new conversation, run `/planner tk-plan`, and confirm it resumes at step 3 without redoing steps 1 and 2. You can stop there; the full six steps aren't needed for the smoke test.

5. **Eval plumbing:** write a small case file and a hand-made `trace.jsonl` with one repeated tool call, run `python3 scripts/eval_checks.py`, and confirm `redundant_calls` fails. Then run `eval-judge` on it with a short hand-written transcript and confirm it returns four separate scores.

6. **Branch check:** run `python3 -m pytest -q tests/test_check_branch_order.py`, then `BASE_REF=main HEAD_REF=feature/x HEAD_REPO=me/r REPO=me/r python3 scripts/ci/check_branch_order.py` and confirm it exits 1, and again with `HEAD_REF=uat` and confirm it exits 0.

Report for each: the mode chosen, which agents ran, test results, and each VERDICT line.

## 12. Verify during the smoke test

These are the parts I couldn't confirm fully from the docs. Test each and tell me the result:

1. **Nested subagents in a worktree.** Subagents can spawn subagents (up to three levels by default) and custom agents can be nested. What I couldn't confirm is whether a subagent spawned by a `workflow-orchestrator` starts inside that orchestrator's worktree or in the main checkout. That's why section 7.3 passes the absolute worktree path down. Check with `pwd` in a nested subagent.
2. **Worktree base.** Worktrees branch from the default branch, not the current HEAD. Confirm each workflow orchestrator's launch-hash check passes, meaning its worktree starts from `dev`'s tip. If worktrees start from `main` instead, `dev` must be the default branch: on GitHub (section 9b) and, locally, `git remote set-head origin dev`. Tell me what you saw in the remote-less smoke test.
3. **Waiting in Mode C.** Subagents launched from the main conversation start in the background by default. Confirm the main orchestrator waits for each result before the next step. If not, apply the `CLAUDE_CODE_FORK_SUBAGENT` note in section 8.
4. **Hook input.** Confirm the PostToolUse input for Edit and Write carries the path at `tool_input.file_path` (log the hook's stdin once to check).
5. **Commands in the extension.** The extension supports a subset of commands. Confirm `/feature`, `/review-pass` and `/codex-ideas` appear when typing `/`.
6. **Codex flags.** Confirm `codex exec --model <m> --sandbox read-only --output-last-message <file> -` works with your installed Codex version.
7. **Skill and planner.** Confirm the main session loads the architecture skill on its own when a contract change comes up, and that the planner subagent can use web search and fetch in step 1.
8. **Model names.** Confirm Codex accepts `gpt-6-sol` and `gpt-6-luna` (for example `codex exec --model gpt-6-luna "say hi"`). If either name is wrong, tell me the names `codex` lists.
9. **Concurrency.** Watch the agent map during the Mode B test and confirm the main orchestrator never has more than 3 subagents running, and that each workflow orchestrator runs its subagents one at a time.
10. **Branch protection.** On the real repo, after I apply section 9b, confirm the `branch-order` check runs on PRs into `main`, `uat` and `dev`, and that a merge into `main` stays blocked until I approve. This needs a paid GitHub plan for a private repo.
