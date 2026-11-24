# Workflow

## 3. Routing: the three modes

The main orchestrator classifies every task before doing anything else and states the classification in one line.

**Simple mode.** All of these are true:
- touches one or at most two files,
- needs no architectural change and no change to any function's input or output contract,
- is easy to test (a few small tests at most),
- doesn't change LLM or agent behaviour (prompts, tool definitions, model calls), since that needs evals.

Route: on the task's own branch off `dev` (section 4b), the unit loop of section 4 in its fast lane, then the branch finish (section 4) → PR into `dev`, reviewed as a whole by pass `pr` → merged.

**Parallel mode** (complex, splits into independent pieces). The task can be split into pieces that can be built at the same time: no piece changes a function or contract that another piece changes or relies on. Pieces that touch the same file in different functions count as independent. Clearly defined and easy to evaluate, even if it touches many files.

Route: the build loop in section 4. The main orchestrator splits the work into tasks, calls a decomposer for each one that's ready and cross-checks the plans. It then hands each checked plan to its own `workflow-orchestrator`, which builds it in its own git worktree, with at most 3 subagents running at once. When they finish, the main orchestrator merges each branch into `dev` by PR, resolving any conflicts itself, and runs a final `pr` review over the merged result, plus a board check.

**Sequential mode** (complex and connected, or sensitive). Any of these is true:
- the pieces have dependencies on each other,
- it needs an architectural or contract change,
- I said it is sensitive or I want to watch it.

Route: the same build loop, but after planning, the main session builds each task itself, one at a time and step by step, on the task's branch in the main checkout, calling each subagent directly. This keeps every subagent visible in the main conversation and in the VS Code agent map, so I can open each trace.

**Overrides.** If my request starts with `simple:`, `parallel:` or `sequential:`, use Simple, Parallel or Sequential mode respectively without classifying.

**Escalation.** No subagent ever changes the architecture on its own, whether the solution architecture or the software architecture; a change to any function's input or output contract counts. A subagent that finds it needs one follows the architecture stop rule in section 4: it writes the proposed change to a file in the run folder and stops. The main session then brings the change to me before anything goes on. Once I've decided, that work moves to Sequential mode, where the main session loads the `architecture` skill. In Parallel mode, a workflow orchestrator that hits this stops and reports back, because the change may affect the other parallel tasks.

**Before routing.** For a new product or a large feature, I may run `/planner` first. Its PRD lists the big architectural tasks with their dependencies; `/build` then builds them with the loop in section 4, decomposing each task only once the tasks it depends on are merged.

## 4. The build loop (Parallel and Sequential modes)

There are two kinds of orchestrator. The **main orchestrator** is the main session: it talks to me, plans every task, cross-checks the plans and merges the results. A **workflow orchestrator** owns one git worktree and builds one checked plan there. In Sequential mode the main session does that building itself.

**Workspace and projects.** Sessions run from the workspace root `~/Developing`, which holds this workflow; each project is a subfolder with its own repo. A task is named `<project>/<task-id>` (for example `task-scheduler/sched-2`); its branches use the task-id alone. Paths here are relative to the root. A subagent working inside a project or worktree uses them as `~/Developing/<path>`, and calls the scripts as `python3 ~/Developing/scripts/<script>` from inside the project or worktree. Git commands run in the project, never in the root (unless the task is about the workflow itself).

Every task gets a run folder `.claude/runs/<project>/<task-id>/` (git-ignored) holding `ask.md` (the request, verbatim), `plan.md`, its eval cases until they're built, and review outputs. A feature that splits into several tasks, or a PRD built with `/build`, also gets a build board, `build-board.md`, in its own run folder: one row per task with its task-id, title, the tasks it depends on, its status (waiting, ready, planning, planned, building, merging, merged or blocked), its branch and a note. The main orchestrator updates the board after every change of status, so a crashed session can resume from it.

**Codex output.** Every call to `~/Developing/scripts/codex_review.py` (GPT-6 Sol or Luna) saves its full output as `review-<pass>-<n>.md` in the task's run folder (next to `ask.md`), or in `--run-dir` when given, with a one-line header of pass, model, base and exit code. The files are numbered, so each round keeps its own review.

**Commit cadence.** Each commit achieves one thing, and its message starts with its story or subtask: `US-n: <what this achieves>`, `test(US-n): ...`, or a plan id such as `X2:`, optionally with `(i/n)` when one subtask spans several commits. There is no line cap: a commit is the size its one goal needs, and a change with two goals is two commits. Never use `--no-verify`.

**Gates (code, not judgement).** The workspace's git hooks (`~/Developing/.githooks/`) run in every repo under `~/Developing`: `pre-commit` runs `ruff check` and `scripts/hooks/slop_checks.py` on the staged Python (`scripts/hooks/lint_gate.py`); `commit-msg` checks the story or subtask id (`scripts/hooks/commit_msg.py`). The root repo's CI runs ruff, the slop checks and the suite on every PR. `ruff.toml` and the slop checks enforce what review rubrics used to judge: types and docstrings, size and complexity, module state, dead code, justification comments. A rule that matters goes into a check, not into prose (see "Correction ratchet").

**Proof of each commit.** No commit is made until the one before it is proven; the review gate in `pre-commit` checks it. A test commit is proven by its `tests` review, an implementation commit by its evidence record, and a commit made by hand (documents, a manual fix) by a `commit` review: `codex-reviewer` runs pass `commit` with `--commit <sha>`. `principles` and `alternatives` run once per branch, in the branch finish, not per commit. A `CHANGES` verdict is decided per finding: *correct* is fixed in a later commit whose message names the fix (`X2: Fix C2 on 875bb0a: ...`); *wrong* or *overstated* is logged with evidence (file:line and the quoted text that contradicts it). A FAIL without a quoted line is dropped, and `wf status` lists what was dropped.

**Decision log.** Every decision (a finding judged, a disputed test, a lane, a pivot or revert, a blocker) gets one row in the run folder's `decisions.tsv`, kept by the `show-me-your-work` skill: append-only, evidence as a pointer, and before the PR another vendor's model reviews the trail. Older runs keep their `decisions-log.md`.

**Correction ratchet.** When the same correction or the same dismissal happens twice (in the decision log, a review, or from me), the next commit on the branch makes it impossible: architecture first, then a ruff rule or a check in `slop_checks.py` or a hook, then a test, prose last (`correct`). A rubric criterion that a check now enforces is removed from the rubric in the same change. Keep the "Rule → what enforces it" table in CLAUDE.md current.

**Concurrency.** At most 3 subagents run at the same time, of any kind. The main orchestrator never has more than 3 running at once, whether decomposers, workflow orchestrators or any other. Each workflow orchestrator runs its own subagents one at a time.

**Driving the engine (`wf`).** In this section `wf` means `~/Developing/.venv/bin/python ~/Developing/scripts/workflow/wf.py` and `<run>` is the task's run folder, as an absolute path. The engine holds the task's state in `<run>/state.json`; nobody edits that file by hand.

1. **Start.** With `ask.md` and the plan in `<run>`, and the task's branch checked out: `wf start <run> --plan plan.md` (Simple and Sequential mode, in the project's main checkout), or `wf start <run> --plan plan.md --checkout <worktree> --mode parallel` (a workflow orchestrator, in its worktree). The session now holds the task: other sessions can't drive it, and this session's edits stay inside it. `wf status <run>` shows where a task is and resumes one after a break.
2. **Ask what is next:** `wf options <run>`. It prints a JSON list.
   - One entry with `"kind": "agent"`: launch the agent it names (`qa` or `implementer`) with the entry's `prompt` as the whole prompt. The prompt starts with the `wf-step:` and `Run folder:` lines the hooks need; a launch without them, or for a step the engine isn't waiting for, is refused. When the agent hands back, its result is recorded for you. If `wf status <run>` still shows that step pending, write the JSON of its `workflow-result` block to `<run>/result.json` and run `wf record <run> <step_id> <run>/result.json`.
   - Entries with `"kind": "decide"`: the engine needs a judgement. Read the review it points at (`<run>/review-<pass>-<n>.md`) and the code or test lines it names, decide each finding on its merits, write the evidence to `<run>/evidence.json` and run `wf take <run> <option> --evidence <run>/evidence.json`. The engine refuses evidence that doesn't fit and says why.
     - `correct` and `overstated`: `{"findings": [{"id": "T2", "reason": "..."}]}`.
     - `wrong`: `{"findings": [{"id": "T2", "reason": "...", "file": "<path>", "line": <n>, "quote": "<that line, exactly>"}]}`; the quoted line is the one that contradicts the finding.
     - `tests_wrong`: `{"test": "<failing test id>", "quote": "<the plan line the test contradicts>"}`. `code_wrong`: `{"tests": ["<failing test id>"]}`.
     - `escalate`: `{"question": "..."}`; it stops the task for me. `architecture_stop`: `{"path": "<the proposal file>"}`; the architecture stop rule below applies.
   - A pending `user` step: the task waits for me. Show me what the engine shows and stop.
3. **Repeat** until `wf status <run>` shows the node `done`. The engine then releases the task. `wf report <run>` prints the decisions, dismissals, commits and dropped findings for the summary.

What the engine does on its own, between those stops: writes the unit, runs the red run, commits the tests, starts and collects the `tests` review, runs the suite, chooses the lane, runs the `impl` review in the full lane, commits the code, writes the evidence record, moves to the next unit, and at the end runs the branch finish. A refused command prints the reason; fix what it names and run it again. Never use `--no-verify`, never commit a unit by hand while the engine is waiting on it, and never edit `state.json`.

`wf release <run> --reason "<why>"` frees a task this session holds without finishing it. It is mine to ask for; a subagent can't run it.

### Plan (main orchestrator, for every task)

1. **Pick ready tasks (just-in-time decomposition).** A task is ready when every task it depends on is merged into dev. Decompose only ready tasks, so a contract or architecture change upstream never forces a plan to be redone.
2. **Decompose, or write a one-unit plan.** A ready task is small when all of these hold, judged from the ask and the code on dev:
   - one goal: one story, delivered as one test commit and one code commit;
   - about 50 lines or fewer of non-test code;
   - 2 or fewer non-test files, plus their test files;
   - its lane is `fast` and its Evals flag is no: no contract, schema or migration change, no risky seam, no security change, no change to LLM or agent behaviour.

   For a small task the main orchestrator writes `plan.md` itself, in the decomposer's format (`decomposer.md`), with one subtask and real `Estimate:` and `Files:` lines, and skips the plan review (step 5). The engine's scope check is the backstop for a low estimate: a change over the larger of 30 lines and twice the estimate, or one that touches a file the plan doesn't name, goes to the `impl` review before it is committed. Where a later step sends a plan back to its decomposer (a clash in step 4, a replan in the build), the main orchestrator revises a one-unit plan itself, or calls a `decomposer` when the task is no longer small.

   Every other task goes to a `decomposer`, up to 3 at a time. Each reads the ask and the code on dev and writes `plan.md` (format in `decomposer.md`): user stories, subtasks with done lines, the files and functions it will touch, the contracts it touches, how it expects to solve the task, an Evals flag and open questions. Workflow orchestrators never decompose; keeping every decomposition in the main session is what lets the plans be cross-checked.
3. **Read each plan.** If its Contracts section lists any changed function, or an `architecture-change-*.md` file exists, apply the architecture stop rule below. If Open questions holds anything that blocks the plan, bring the questions to me.
4. **Cross-check.** The main orchestrator compares the new plans with each other and with the plans of tasks still building, and writes what it found to `cross-check.md` in the board's run folder. A clash is two plans changing the same function or contract, one plan relying on a function or contract that another changes, or two plans building the same thing. Touching the same file in different functions is not a clash. It sends each clash back to the decomposers concerned with full context (their own plan, the other plan and the clash), then checks again. After 3 rounds with a clash left, it builds one of the two tasks now and holds the other back, to be decomposed again once the first is merged; if neither can wait, it brings the clash to me.
5. **Review each plan.** `codex-reviewer` runs pass `plan` (GPT-6 Sol). If the verdict is `CHANGES`, send the findings back to `decomposer` once, and cross-check that plan again if it changed.
6. **Create evals (only if the Evals flag is yes).** The main session writes the eval cases with me, using `/eval-create` (section 5b). They stay in the task's run folder until the task is built.

Each checked plan then goes to the build. In Parallel mode the main orchestrator first creates the task's worktree from the project's `dev`: `git -C <project> worktree add ~/Developing/.worktrees/<project>/<task-id> -b feature/<task-id> dev` (`bugfix/` for a bug). It then hands the plan to a new `workflow-orchestrator`, with the worktree's absolute path, the branch, the launch hash, the full text of `ask.md`, `plan.md`, any approved `architecture.md` and the eval cases. In Sequential mode the main session builds it, one task at a time.

### Build (a workflow orchestrator in Parallel mode, the main session in Sequential mode)

1. **Set up.** Work on the task's own branch, starting from dev's tip (section 4b). Write the plan files to the run folder and the eval cases to `evals/cases/`.
2. **Unit loop, one plan subtask at a time.** The workflow engine (`wf`, `scripts/workflow/wf.py`) owns the order: it names each step, makes every commit, runs the tests, starts each review and writes each evidence record. The main session (Sequential mode) or the workflow orchestrator (Parallel mode, with `wf start --checkout <worktree> --mode parallel`) asks `wf options`, launches the agent the engine names with the prompt it gives, and decides with evidence where the engine asks (`wf take`). qa and the implementer never commit. The steps below are what the engine does.
   1. **Lane.** The decomposer tags each subtask `fast` or `full`. Full: it changes a contract, a schema or migration, a risky seam (auth, network, an external service, deploy configuration) or security; everything else is fast. Every unit gets the `tests` review of its test commit; full adds the `impl` review of the uncommitted code before it is committed. Single purpose: a fast unit takes the full lane anyway when its change touches a code file its `Files:` line doesn't name, or is over the larger of 30 lines and twice its `Estimate:`.
   2. **Tests first.** `qa` writes tests under `tests/` for the subtask, named after its story, testing behaviour through public contracts (the two-edit test in `qa.md`). It runs them and confirms they fail for the expected reason. Every added test must fail before the code exists: a case that already passes is left out, and the engine's red run refuses a test commit that holds one. It returns only its result block. For a bug, the failing test reproduces the bug (`tdd` skill).
   3. **Commit the failing tests.** The main session commits qa's tests on their own (`test(US-n): ...`), seen red (`principle-sequence-verifiable-units`: the failing test first, then the fix). The `tests` review of that commit (the spec: do these tests check the done line and the stories through public contracts?) runs in the background, in a worktree at the commit, while the implementer works. The branch may be red between this commit and the fix; the suite is green again before the next subtask starts.
   4. **Implement until green.** `implementer` writes the code and iterates on its own until the unit's tests, the full suite, `ruff check` and `slop_checks.py` pass. It never edits tests; a test it believes is wrong stays failing and goes in `tests_disputed`. It returns only its result block.
   5. **Verify.** Before the fix is committed, the engine collects the `tests` review of the test commit, and its findings are decided (proof of each commit, above): a finding that is right sends the tests back to qa, and the fix is committed only against tests whose review is settled. The engine then checks `git diff` shows no change under `tests/`, reruns the suite itself, and any disputed test is decided with evidence (*tests wrong*: quote the plan or ask line the test contradicts → back to qa; otherwise → back to the implementer).
   6. **Commit and prove.** Commit the fix (the hooks run the gates), then run `python3 scripts/hooks/evidence_record.py write --run <run folder>`. It measures the evidence itself: every added test red at the test commit and green now, the suite green apart from declared `Breaks:`, no `tests/` edits, no uncovered signature change. The commit is accepted on that record, not on a model reading the code. In the full lane, the `impl` review reads the code as well. A manual commit, such as docs, may use a `commit` review instead.
   **Design and contracts.** Before code that sets a new shape, sketch it with `architect`. The `principle-redesign-from-first-principles` and `principle-migrate-callers-then-delete-legacy-apis` skills apply; when they change a public contract, the `architecture` skill runs first and waits for my approval (CLAUDE.md). A migration may delete tests that only protected the old implementation, naming each one in the commit message.
   **Planned breakage.** Within a rewrite or migration whose plan I approved with declared phase boundaries, intermediate commits on the task branch may leave declared parts failing (`principle-outcome-oriented-execution`). The branch is fully green, with the full suite and every gate, before the branch finish; nothing red is merged into dev.
   Stop after 3 rounds back to the same step within one subtask and report what blocks.
3. **Branch finish.** After the last subtask:
   1. **Subtract.** Run `deslop` and `no-comments` over the branch diff against the launch hash. Their edits are a commit like any other (gates, evidence record). Behaviour and tests stay the same.
   2. **Principles and alternatives,** once over the whole branch: `codex-reviewer` runs both with `--base <launch hash>` and no `--commit` on a clean tree. Decide findings as for commit reviews.
   3. **Full suite** once.
4. **Writing.** Reports, PR descriptions and summaries for me follow `unslop`; docs and READMEs also follow `technical-writing`. The PR itself is opened or updated with the `visual-pr` skill (one-sentence why, 1–3 notes, a structural change outline). Plans and options are shown visually where that's clearer (`show-me`).
5. **Run evals (only if the Evals flag is yes).** For each case: `eval-runner` plays the user, `~/Developing/scripts/eval_checks.py` runs the code checks, and `eval-judge` scores the run (section 5b).
6. **Final review.** `codex-reviewer` runs pass `answers-ask` (GPT-6 Luna) with the launch hash as the base. It reads the plan, every commit's message and file stats, and each saved review verdict, not the diff: every commit was proven before the next was made.
7. **Decide.**
   - all tests pass, every eval case passes, and `answers-ask` is `PASS` → done: the branch is a series of reviewed commits (`alternatives` findings are reported, not acted on, unless one is clearly better and cheap),
   - tests fail, an eval case fails, or review finds a defect in the code → back to step 2,
   - review or evals show the plan itself was wrong, or the tests don't test the real ask → back to Plan: a workflow orchestrator stops and reports STATUS: REPLAN with the reason; the main orchestrator sends that reason to `decomposer`, then cross-checks and reviews the new plan before it's built again,
   - any subagent reports `ARCHITECTURE CHANGE`, or a review finding can only be fixed by an architecture change → follow the architecture stop rule below.

Stop after **3** rounds through step 7 and report to me with what is blocking, rather than looping further.

### Merge (main orchestrator)

For each finished task, one branch at a time, working in that task's worktree (Parallel mode) or the main checkout (Sequential mode):

1. Fetch and merge the latest dev into the branch. The main orchestrator resolves any conflict itself. If a conflict can only be resolved by changing a contract or the architecture, it applies the architecture stop rule.
2. `qa` runs the full suite on the branch.
3. Push the branch and open a PR into dev with the `visual-pr` skill. Before that, run `blast-radius` on any change you don't fully trust. `codex-reviewer` runs pass `pr` (GPT-6 Sol) over the full PR with `--base dev`, the PR's target (it diffs from where the branch last met dev, so dev's commits merged in are left out); with no remote, run it before the local merge. Fix a `CHANGES` verdict in new commits, each reviewed by the commit cadence, then run `pr` again (at most 3 rounds, then report to me). When `pr` passes, keep the task's records in its project: copy from the run folder `ask.md`, `plan.md`, `architecture.md` (if any), `decisions.tsv`, every `review-*.md` and every `evidence-*.json`, and the output of `wf report <run>` as `report.md`, into `<project>/docs/evidence/<task-id>/`, and commit only that folder on the branch with the subject `X0: Records of <task-id>`. Then wait for the checks and merge it (section 4b).
4. Remove the worktree (`git -C <project> worktree remove ~/Developing/.worktrees/<project>/<task-id>`), pull dev in the project's main checkout, and mark the task merged on the board.

When every task launched together is merged, review the combined result in two parts. **Board check** (the main orchestrator, no model): every task launched together is marked merged on the board, and each one's own `answers-ask` and `pr` reviews ended in `PASS` or a fix. **Cross-task review:** `codex-reviewer` runs pass `pr` (GPT-6 Sol) on `dev` with `--base <launch hash>`, `--ask-file` the top-level `ask.md` and `--plan-file` the `build-board.md`, looking for problems between tasks: duplication, clashing contracts, one task undoing another. A `CHANGES` verdict becomes a new `bugfix/` task on the board. Then the board's newly ready tasks go back to Plan.

**Architecture stop rule (every subagent).** If any subagent finds it needs to change the architecture, whether the solution architecture or the software architecture (a public function's input or output contract counts), it does not make the change. It writes the proposed change to `architecture-change-<agent name>.md` in the run folder (what must change, why, what it affects, and the options it sees), stops, and reports `ARCHITECTURE CHANGE: <path to that file>`. A workflow orchestrator that receives that report, or that finds a review finding needs an architecture change, stops its loop and reports the same line to the main session. The main session then shows me the file and waits for my decision. Until I decide, it starts no new work on that task and merges nothing from Parallel mode.

## 4b. Branches and environments

| Branch | Environment | Takes changes from |
| --- | --- | --- |
| `main` | production | `uat` only, by PR, with my approval |
| `uat` | UAT | `dev` or `hotfix/*`, by PR |
| `dev` | dev | `feature/*`, `bugfix/*` or `hotfix/*`, by PR |

- Nothing is committed to `main`, `uat` or `dev` directly. Everything arrives by PR.
- Every task works on its own branch off an up-to-date `dev`: `feature/<task-id>` for a feature, `bugfix/<task-id>` for a bug, and `hotfix/<task-id>` only when I call it a hotfix. In Parallel mode, each workflow orchestrator's worktree is its task's branch.
- Before any work starts, the project's main checkout must be on `dev`, clean and up to date: `cd <project> && git switch dev`, `git status --porcelain` printing nothing, then `git pull --ff-only`. If there are uncommitted changes, stop and ask me what to do with them; never commit them to `dev`. The launch hash is `dev`'s tip after the pull (`git rev-parse HEAD`).
- Use merge commits (`gh pr merge --merge`), never squash or rebase merges, so the histories of `dev`, `uat` and `main` stay compatible.
- Agents may, on their own: merge a task's PR into `dev` once its checks pass (`gh pr create --base dev --fill`, `gh pr checks --watch`, `gh pr merge --merge`); promote `dev` to `uat` with a PR from `dev` into `uat`, merged once its checks pass; and send a hotfix to `uat` with a PR from its `hotfix/` branch, as well as to `dev`.
- When I ask for a release, open a PR from `uat` into `main` and stop. Never approve or merge a PR into `main`; I do that.
- Merging into `dev` or `uat` may deploy that environment; that's allowed. Nothing reaches production without my approval.
- If the repo has no GitHub remote (as in the smoke test), merge into `dev` locally with `git merge --no-ff <branch>` instead of a PR, and say so. That's the only exception.
- `.github/workflows/branch-order.yml` (section 7.26) checks every PR's source branch against the table above. Branch protection (section 9b) makes PRs and my approval on `main` mandatory; I apply it by hand.
- One session per task, and one worktree per session. A session drives at most one task and touches only that task's run folder, checkout and branch; other tasks are read-only to it. `wf` records the owner in `.claude/runs/.active/<project>--<task-id>.json` and refuses a task another live session holds; the `PreToolUse` guards refuse launches off the graph and edits outside the task, and `pre-commit` refuses a branch another session holds. A stale claim (its process is gone) is taken over and logged; only I free a live one, with `wf release <run> --reason ...`. Each session's worktree is `.worktrees/<project>/<task-id>/`; when other sessions are active, change the workflow from a root worktree, not the root checkout, and keep the root checkout on `dev`.

## 5. Review passes

Each pass is narrow on purpose. Each lives in `.claude/review-passes/<pass>.md` and is run by `~/Developing/scripts/codex_review.py`, which picks the model by pass.

**GPT-6 Sol, open-ended:**

- **pr** (once per PR, the PR's own diff from where it last met `--base dev`; needs `--base`, the ask and the plan): looks only for problems no single commit shows: the same thing built twice, a later commit undoing an earlier one, leftover or dead code, inconsistency across files, pieces whose contracts don't fit together.

- **plan**: does the plan, if executed, deliver the ask? Missing subtasks, wrong order, hidden contract changes, untestable steps, done lines that don't match their stories.
- **ideas** (via the `wild-card` agent and `/codex-ideas`): bold, unconventional approaches to the ask. Most will be wrong. Opus rates each one and adopts one only if it clearly beats the current plan, and never without my yes.

**GPT-6 Luna, with a fixed rubric.** Luna is fast and cheap but reliable only with a clear rubric, so each pass answers every criterion with PASS, FAIL or N/A plus evidence (file and line). The verdict is `CHANGES` if any criterion is FAIL.

- **tests** (one unit's test commit, `--commit <sha>`, with `unit.md` and the red run): judges the unit's tests as its spec. T1 they check planned behaviour through the public contract; T2 the done line and the plan's edge cases are covered, without asking for a case that already passes before the code; T3 no assertion a trivial stub would pass; T4 a broken behaviour fails a test and a different implementation of the same behaviour doesn't.
- **impl** (one unit's uncommitted code, no `--commit`, with `unit.md` and `architecture.md`; the full lane only): I1 the code does what the unit asks and nothing else, and stays in the unit's files; I2 no special-casing of test inputs; I3 no contract change outside an approved `architecture.md`.
- **commit** (one commit made by hand, `--commit <sha>`; needs the ask and the plan): sees that commit's message and diff, plus the one-line log of earlier commits.
  - C1. The message states one clear goal (its story or subtask id is checked by the `commit-msg` hook).
  - C2. The diff does what the message says, fully.
  - C3. The diff does nothing the message doesn't say.
  - C4. The goal is a step toward the ask and the plan, not a detour or a change the plan doesn't call for.
  - C5. No test gaming (hard-coded expected outputs, special-casing test inputs), and no test deleted, skipped or loosened, except a test that only protected an old implementation in an approved migration, or one that passed before its unit's implementation existed.
- **answers-ask** (whole branch; needs `--base`, the ask and the plan): sees every commit's message and file stats and each commit's verdict, never the diff.
  - A1. Every user story in `plan.md` is delivered by commits you can name (sha and message).
  - A2. Every subtask's done line is met by a named commit.
  - A3. For a bug: a commit names the fix for the reported failing case and its test.
  - A4. Every saved `CHANGES` verdict has each finding fixed by a later commit that names it, or dismissed in the decision log. A commit with no saved verdict was accepted on its evidence record.
  - A5. No commit deletes, skips or loosens a test, judging from its message, its file stats and its review.
  - A6. Every file changed belongs to a subtask in the plan.
- **principles** (once per branch, `--base <launch hash>`): types, docstrings, size and module state are checked by ruff and `slop_checks.py` before review, so the rubric keeps only judgement calls.
  - P1. Each new or changed function has one purpose.
  - P3. No public function's signature or output shape changed, unless an approved `architecture.md` covers it.
  - P5. Functions use other functions only through their contracts, not their internals.
  - P6. Each module keeps one clear responsibility.
- **alternatives** (once per branch, `--base <launch hash>`):
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
- **Code checks** (cheap, no model): `python3 ~/Developing/scripts/eval_checks.py <run dir> <case file>` checks tool-call count, redundant calls (the same tool with the same arguments more than once), total tokens and wall time against the case's budgets, and writes `checks.json`.
- **Judge** (`eval-judge`, GPT-6 Luna): reads the case, the transcript, the full trace and `checks.json` against the rubric in `.claude/review-passes/judge.md`, and scores 1 to 5, with evidence, four separate dimensions: whether each tool call makes sense (`tool_use`), groundedness against tool outputs (`groundedness`), whether it answers the question (`answers_question`), and completeness (`completeness`). It writes `scores.json`.

A case passes only when every code check passes and every dimension meets the case's threshold.

**Calibration.** `/eval-calibrate <run-id>`: I grade a few transcripts by hand on the same four dimensions, without seeing the judge's scores. The main session compares my grades with the judge's per dimension and proposes rubric fixes where we differ by more than a point; it changes the rubric only with my yes.

**Ownership.** The implementer never edits anything under `evals/` or the judge rubric. The harness lives outside `evals/` because it's ordinary code.

## 3b. Interview route (`interview:`)

A light pass for time-boxed demos (about 90 minutes). It keeps the checkpoints that show judgment and drops the heavy machinery. Everything else in this document still applies, including the architecture stop rule and the branch flow. State at the start that this is the short route and that the full process is the one above.

Route, one task at a time, in the main session:
1. Check the project's main checkout is on dev, clean and up to date (section 4b). Create `feature/<task-id>` (or `bugfix/<task-id>`) off dev. Write `ask.md` to `.claude/runs/<project>/<task-id>/`.
2. Call one `decomposer` to write `plan.md`, or, for a small task (section 4, Plan step 2), write the one-unit plan yourself. No cross-check and no plan review. If its Contracts section lists any changed function, or it reports `ARCHITECTURE CHANGE`, apply the architecture stop rule.
3. **Checkpoint:** show me `plan.md` and wait until I approve it. Tell me in a few lines what to check.
4. `qa` writes tests; the main session commits them (commit cadence and gates, section 4). **Checkpoint:** confirm they fail because the feature is missing, and say so.
5. `implementer` builds until green; the main session reruns the full suite and commits. If tests fail, back to the implementer.
6. Review: run `codex-reviewer` pass `commit` on each commit, then `answers-ask`. If `codex` isn't installed or signed in, skip the review, say so in the summary, and never pretend it ran.
7. If the verdict is `CHANGES`, one fix round (back to step 5, then review again). If it still fails, stop and report what blocks.
8. Run pass `pr` over the full branch with `--base dev`, before the merge (when the PR opens, or before a local merge), with one fix round. Then merge the task's branch, already a series of commits within the cadence, into dev (by PR, or `git merge --no-ff` locally if there is no remote). Finish with a short summary: what was built, test result, the review verdict or that it was skipped, and what is left.

Not used in this route: mode classification, cross-checking, plan review, `principles` and `alternatives` passes, evals, `/codex-ideas`, parallel worktrees, and the planner's six steps. Planning for an interview uses the `light-planner` skill.
