# Developing: agentic development workspace

This folder is the development workspace and its own git repo (`gacuchac/agentic-developing`). It holds the workflow: agents, commands, skills, review passes, hooks and scripts. Each subfolder is a project with its own git repo, its own tests and its own CI. Sessions always open here; all development happens from here into the projects.

## Layout
- `.claude/`: agents, commands, skills, review passes, `workflow/loop.md`, `settings.json` (Claude Code hooks). Only here, never copied into a project.
- `scripts/`: workflow scripts (`codex_review.py`, `eval_checks.py`, `hooks/`, `ci/`, `new_project.py`).
- `.githooks/`: git hooks for every repo under this folder, enabled once by the global git config (README).
- `templates/project/`: what a new project starts from (CLAUDE.md, .gitignore, CI). Copied once by `scripts/new_project.py`, never synced.
- `tests/`: tests of the workflow scripts. `docs/`: reference docs.
- `.claude/runs/<project>/<task-id>/`: per-task working files (git-ignored). `.worktrees/<project>/<task-id>/`: Parallel-mode worktrees (git-ignored).
- Agents a project ships as part of its product (for example a chatbot's agent) are project code in the project's own folders, not `.claude/` agents.

## Coding principles (all projects)
- Cohesive and modular: each module has one clear responsibility.
- Lean functional: prefer pure, stateless functions. Object-oriented code is fine where it fits, but methods still follow the rules below.
- One purpose per function. Internal helper functions inside a class or module are fine, as long as the behaviour is encapsulated.
- Clear input and output contracts. Each public function has typed inputs and outputs and a docstring that states the contract.
- Contracts are stable. A change or bug fix inside a function must not force any caller to change, as long as the output keeps the same shape and meaning. Fix the function so downstream code keeps working unchanged.
- Changing a contract is an architectural change. It goes through the `architecture` skill in the main session and is never handed to the implementer.
- No subagent changes the solution architecture or the software architecture itself. It writes the proposed change to a file in the run folder and stops, and the main session brings it to me before anything goes on.
- Functions don't depend on hidden state or on the internals of other functions; only on their contracts.
- Workflow scripts are Python only.

## How work is routed
You are the main orchestrator. For every feature or bug:
1. Name the project (subfolder) it belongs to, or this root if it changes the workflow itself; ask me if unclear. Run every git command in that project (`git -C <project> ...` or `cd <project> && ...`).
2. Classify it as Mode A (simple), B (complex, parallelizable) or C (complex, sequential or sensitive) using the rules in @.claude/workflow/loop.md, and state the project and the mode in one line.
3. Honour overrides: a request starting with `simple:`, `parallel:` or `sequential:` forces Mode A, B or C. A request starting with `interview:` uses the interview route (section 3b of @.claude/workflow/loop.md), a light pass for time-boxed demos. Skills `light-planner` (interview version of `/planner`) and `light-build` (this route) start from plain requests such as "light planner" or "light build".
4. Follow the route for that mode in @.claude/workflow/loop.md.
5. Never let the implementer change a function contract. For any contract or architectural change, load the architecture skill, show me its proposal and wait for my approval before anyone edits code.
6. When any subagent reports `ARCHITECTURE CHANGE: <file>`, stop that work, show me the file, and wait for my decision before anything goes on. Start no new work on that task and merge nothing from Mode B until I decide.
7. For a new product or large feature, I may run /planner first; then build the PRD with /build.
8. You call every decomposer yourself; workflow orchestrators never decompose. Cross-check the plans before anything is built, and decompose a task only once every task it depends on is merged into dev.
9. At most 3 subagents run at the same time, of any kind. Each workflow orchestrator runs its own subagents one at a time.
10. When a plan's Evals flag is yes, write the eval cases with me using /eval-create before that task is built.
11. Never commit to main, uat or dev directly, in any repo. Each task gets a feature/, bugfix/ or hotfix/ branch off a clean, up-to-date dev of its project and comes back by PR. If a checkout has uncommitted changes, stop and ask me. You may merge PRs into dev and promote dev or a hotfix to uat. Never approve or merge a PR into main; I do that.

## Conventions
- Python, tests with pytest under each project's tests/. Run them with the project's `.venv/bin/python -m pytest` when it has a `.venv`, else `python3 -m pytest`. Use `set -o pipefail` when piping test output.
- Eval cases are written to the task's run folder, then committed to evals/cases/ in the project on the task's branch; eval runs go in the project's evals/runs/ (git-ignored). The implementer never edits evals/.
- Branches map to environments: dev to dev, uat to UAT, main to production. Merging into dev or uat may deploy that environment, which is allowed; nothing reaches production without my approval.
- Quick deploys outside that flow use my personal Railway and GitHub accounts. Deploy only when I ask.
