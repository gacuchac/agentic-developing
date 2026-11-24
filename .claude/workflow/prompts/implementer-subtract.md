wf-step: {step_id}
Run folder: {run}
Agent: implementer
Step: subtract
Repo: {repo}

This is the branch finish. Read the branch's whole diff (`git diff <launch hash>..HEAD`; the launch hash is `launch` in the run folder's `state.json`) and remove AI code slop without changing behaviour, following the `deslop` and `no-comments` skills in `~/Developing/.claude/skills/`: narrating comments, defensive checks on trusted paths, needless layers, duplication, dead code.

The last unit of the plan, for context only:

{unit}

Rules:
- Work only inside the repo above. Before starting, read the Approach and Contracts sections of the plan on the `Plan:` line: they hold decisions that apply to every unit. Run tests with the interpreter on the `Python:` line (`<Python> -m pytest -q`) in place of any `.venv` or `python3` rule. Keep every public contract and its docstring. Never edit files under `tests/`.
- If nothing is worth removing, change nothing.
- After any edit the whole suite must pass, and `ruff check --config ~/Developing/ruff.toml <changed files>` and `python3 ~/Developing/scripts/hooks/slop_checks.py <changed .py files>` must be clean.
- Do not stage or commit.

Reply with only this block. `removed` is a short phrase naming what you removed, or an empty string when you changed nothing. `files` maps each changed path to its changed line count, or is empty.
```workflow-result
{schema}
```
