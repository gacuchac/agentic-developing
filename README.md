# agentic-developing

The development workspace: a multi-model agent workflow for Claude Code (Opus orchestrates, Sonnet builds, GPT-6 Sol and Luna review through the Codex CLI). Each project is a subfolder with its own git repo, tests and CI; the workflow lives only here. Layout and rules: [CLAUDE.md](CLAUDE.md). Full spec: [docs/multi-agent-setup.md](docs/multi-agent-setup.md).

## Set up once per machine
1. Clone this repo to `~/Developing`.
2. `git config --global includeIf.gitdir:~/Developing/.path ~/Developing/.gitconfig-workflow`: turns on the git hooks for every repo under `~/Developing`, and nowhere else: ruff and the slop checks on staged Python, the review gate (no commit until the previous one has a saved review), and the commit-subject check.
3. `python3 -m venv .venv && .venv/bin/pip install pytest pyyaml hypothesis`, for the workflow's own tests.
4. Codex CLI installed and signed in (`codex login`); `ruff` for the lint hook; `gh` signed in as the agents' account.

## Use
- Always open VS Code at `~/Developing`, never inside a project, and pick Opus.
- New project: `python3 scripts/new_project.py <name> "<what it is>"`, then make its `.venv`.
- Work: `/feature <project>: <description>` (force a mode with `simple:`, `parallel:`, `sequential:` or `interview:`).
- Larger work: `/planner <project>/<task-id> <description>`, then `/build <project>/<task-id>`.
- Reviews and ideas: `/review-pass <pass> <project>/<task-id>`, `/codex-ideas <project>/<task-id>`.
- Evals: `/eval-create <project>/<task-id>`, `/eval-calibrate <run-id>`.

## Changing the workflow
This repo follows its own rules: a `feature/` branch off `dev`, commits of at most 30 changed lines, a PR into `dev`. Its tests: `.venv/bin/python -m pytest -q`.
