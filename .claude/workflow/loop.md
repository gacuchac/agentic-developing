# Workflow

## 3. Routing: the three modes

The main orchestrator classifies every task before doing anything else and states the classification in one line.

**Mode A: Simple.** All of these are true:
- touches one or at most two files,
- needs no architectural change and no change to any function's input or output contract,
- is easy to test (a few small tests at most),
- doesn't change LLM or agent behaviour (prompts, tool definitions, model calls), since that needs evals.

Route: on the task's own branch off `dev` (section 4b): `implementer`, committing by the commit cadence (section 4) → `qa` runs tests → `codex-reviewer` passes `commit` and `principles` on each commit, then `answers-ask` → done, or one fix round → PR into `dev`, reviewed as a whole by pass `pr` → merged.

**Mode B: Complex and parallelizable.** The task can be split into pieces that can be built at the same time: no piece changes a function or contract that another piece changes or relies on. Pieces that touch the same file in different functions count as independent. Clearly defined and easy to evaluate, even if it touches many files.

Route: the build loop in section 4. The main orchestrator splits the work into tasks, calls a decomposer for each one that's ready and cross-checks the plans. It then hands each checked plan to its own `workflow-orchestrator`, which builds it in its own git worktree, with at most 3 subagents running at once. When they finish, the main orchestrator merges each branch into `dev` by PR, resolving any conflicts itself, and runs a final `pr` review over the merged result, plus a board check.

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

**Codex output.** Every call to `scripts/codex_review.py` (GPT-6 Sol or Luna) saves its full output as `review-<pass>-<n>.md` in the task's run folder (next to `ask.md`), or in `--run-dir` when given, with a one-line header of pass, model, base and exit code. The files are numbered, so each round keeps its own review.

**Commit cadence.** Every commit has at most 30 changed lines: per file, the larger of lines added and lines deleted; tests and eval cases count; merges are exempt. The `pre-commit` hook in `.githooks/` enforces it. Each commit achieves one thing, and its message starts with its story or subtask: `US-n: <what this achieves>`, or `test(US-n): ...` for tests. If a step can't fit in 30 lines, split it; if it can't be split, the approach is probably wrong, so say so instead of forcing it. Never use `--no-verify`. Each new commit is reviewed on its own, oldest first (`git rev-list --reverse <last reviewed>..HEAD`): `codex-reviewer` runs pass `commit` (the ask, the plan and the earlier commits give it the big picture), then `principles` and `alternatives`, each with `--commit <sha>`. A `CHANGES` verdict is fixed in a later commit whose message names the fix.

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
2. **Write tests.** `qa` writes tests for the plan under `tests/`, each named after the user story it checks, and confirms they fail for the right reason. It commits them by the commit cadence.
3. **Implement.** `implementer` builds each subtask, committing by the commit cadence. It never edits tests or evals. Then every new commit, tests included, is reviewed on its own (commit cadence); a `CHANGES` verdict goes back to the implementer.
4. **Run tests.** `qa` runs the new and affected tests first and reports pass/fail with the failing output. Once they pass, it runs the full suite once before the final review.
5. **Run evals (only if the Evals flag is yes).** For each case: `eval-runner` plays the user, `scripts/eval_checks.py` runs the code checks, and `eval-judge` scores the run (section 5b).
6. **Final review.** `codex-reviewer` runs pass `answers-ask` (GPT-6 Luna) with the launch hash as the base. It reads the plan, every commit's message and file stats, and each commit's verdict, not the diff, which was reviewed commit by commit.
7. **Decide.**
   - all tests pass, every eval case passes, and `answers-ask` is `PASS` → done: the branch is a series of reviewed commits (`alternatives` findings are reported, not acted on, unless one is clearly better and cheap),
   - tests fail, an eval case fails, or review finds a defect in the code → back to step 3,
   - review or evals show the plan itself was wrong, or the tests don't test the real ask → back to Plan: a workflow orchestrator stops and reports STATUS: REPLAN with the reason; the main orchestrator sends that reason to `decomposer`, then cross-checks and reviews the new plan before it's built again,
   - any subagent reports `ARCHITECTURE CHANGE`, or a review finding can only be fixed by an architecture change → follow the architecture stop rule below.

Stop after **3** rounds through step 7 and report to me with what is blocking, rather than looping further.

### Merge (main orchestrator)

For each finished task, one branch at a time, working in that task's worktree (Mode B) or the main checkout (Mode C):

1. Fetch and merge the latest dev into the branch. The main orchestrator resolves any conflict itself. If a conflict can only be resolved by changing a contract or the architecture, it applies the architecture stop rule.
2. `qa` runs the full suite on the branch.
3. Push the branch and open a PR into dev. `codex-reviewer` runs pass `pr` (GPT-6 Sol) over the full PR with `--base dev`, the PR's target (it diffs from where the branch last met dev, so dev's commits merged in are left out); with no remote, run it before the local merge. Fix a `CHANGES` verdict in new commits, each reviewed by the commit cadence, then run `pr` again (at most 3 rounds, then report to me). Then wait for the checks and merge it (section 4b).
4. Remove the worktree, pull dev in the main checkout, and mark the task merged on the board.

When every task launched together is merged, review the combined result in two parts. **Board check** (the main orchestrator, no model): every task launched together is marked merged on the board, and each one's own `answers-ask` and `pr` reviews ended in `PASS` or a fix. **Cross-task review:** `codex-reviewer` runs pass `pr` (GPT-6 Sol) on `dev` with `--base <launch hash>`, `--ask-file` the top-level `ask.md` and `--plan-file` the `build-board.md`, looking for problems between tasks: duplication, clashing contracts, one task undoing another. A `CHANGES` verdict becomes a new `bugfix/` task on the board. Then the board's newly ready tasks go back to Plan.

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

- **pr** (once per PR, the PR's own diff from where it last met `--base dev`; needs `--base`, the ask and the plan): looks only for problems no single commit shows: the same thing built twice, a later commit undoing an earlier one, leftover or dead code, inconsistency across files, pieces whose contracts don't fit together.

- **plan**: does the plan, if executed, deliver the ask? Missing subtasks, wrong order, hidden contract changes, untestable steps, done lines that don't match their stories.
- **ideas** (via the `wild-card` agent and `/codex-ideas`): bold, unconventional approaches to the ask. Most will be wrong. Opus rates each one and adopts one only if it clearly beats the current plan, and never without my yes.

**GPT-6 Luna, with a fixed rubric.** Luna is fast and cheap but reliable only with a clear rubric, so each pass answers every criterion with PASS, FAIL or N/A plus evidence (file and line). The verdict is `CHANGES` if any criterion is FAIL.

- **commit** (one commit, `--commit <sha>`; needs the ask and the plan): sees that commit's message and diff, plus the one-line log of earlier commits.
  - C1. The message states one clear goal and names its story or subtask (US-n or subtask n).
  - C2. The diff does what the message says, fully.
  - C3. The diff does nothing the message doesn't say.
  - C4. The goal is a step toward the ask and the plan, not a detour or a change the plan doesn't call for.
  - C5. No test gaming (hard-coded expected outputs, special-casing test inputs), and no test deleted, skipped or loosened.
- **answers-ask** (whole branch; needs `--base`, the ask and the plan): sees every commit's message and file stats and each commit's verdict, never the diff.
  - A1. Every user story in `plan.md` is delivered by commits you can name (sha and message).
  - A2. Every subtask's done line is met by a named commit.
  - A3. For a bug: a commit names the fix for the reported failing case and its test.
  - A4. Every commit has a `commit` review verdict, and each `CHANGES` is followed by a later commit that names the fix.
  - A5. No commit deletes, skips or loosens a test, judging from its message, its file stats and its review.
  - A6. Every file changed belongs to a subtask in the plan.
- **principles** (run per commit, with `--commit <sha>`):
  - P1. Each new or changed function has one purpose.
  - P2. Each public function has typed inputs and outputs and a docstring that states its contract.
  - P3. No public function's signature or output shape changed, unless an approved `architecture.md` covers it.
  - P4. No function relies on hidden or global mutable state.
  - P5. Functions use other functions only through their contracts, not their internals.
  - P6. Each module keeps one clear responsibility.
- **alternatives** (run per commit, with `--commit <sha>`):
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

## 3b. Interview route (`interview:`)

A light pass for time-boxed demos (about 90 minutes). It keeps the checkpoints that show judgment and drops the heavy machinery. Everything else in this document still applies, including the architecture stop rule and the branch flow. State at the start that this is the short route and that the full process is the one above.

Route, one task at a time, in the main session:
1. Check the main checkout is on dev, clean and up to date (section 4b). Create `feature/<task-id>` (or `bugfix/<task-id>`) off dev. Write `ask.md` to `.claude/runs/<task-id>/`.
2. Call one `decomposer` to write `plan.md`. No cross-check and no plan review. If its Contracts section lists any changed function, or it reports `ARCHITECTURE CHANGE`, apply the architecture stop rule.
3. **Checkpoint:** show me `plan.md` and wait until I approve it. Tell me in a few lines what to check.
4. `qa` writes and commits tests (commit cadence, section 4). **Checkpoint:** confirm they fail because the feature is missing, and say so.
5. `implementer` builds; `qa` runs the new and affected tests, then the full suite once. If tests fail, back to the implementer.
6. Review: run `codex-reviewer` pass `commit` on each commit, then `answers-ask`. If `codex` isn't installed or signed in, skip the review, say so in the summary, and never pretend it ran.
7. If the verdict is `CHANGES`, one fix round (back to step 5, then review again). If it still fails, stop and report what blocks.
8. Run pass `pr` over the full branch with `--base dev`, before the merge (when the PR opens, or before a local merge), with one fix round. Then merge the task's branch, already a series of commits within the cadence, into dev (by PR, or `git merge --no-ff` locally if there is no remote). Finish with a short summary: what was built, test result, the review verdict or that it was skipped, and what is left.

Not used in this route: mode classification, cross-checking, plan review, `principles` and `alternatives` passes, evals, `/codex-ideas`, parallel worktrees, and the planner's six steps. Planning for an interview uses the `light-planner` skill.
