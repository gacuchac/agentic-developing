wf-step: {step_id}
Run folder: {run}
Agent: implementer
Step: code
Repo: {repo}

Write the code that makes this unit's committed tests pass, and nothing else.

{unit}

Rules:
- Work only inside the repo above. Before starting, read the Approach and Contracts sections of the plan on the `Plan:` line: they hold decisions that apply to every unit. Run tests with the interpreter on the `Python:` line (`<Python> -m pytest -q`) in place of any `.venv` or `python3` rule.
- Iterate until the unit's tests and the whole suite pass, and `ruff check --config ~/Developing/ruff.toml <changed files>` and `python3 ~/Developing/scripts/hooks/slop_checks.py <changed .py files>` are clean.
- Change only what this unit needs: one goal, the one in its title. If the unit turns out to hold two goals, say so in one line above the block and name where it could split.
- Never edit files under `tests/`. A test you believe is wrong stays failing and goes in `tests_disputed` with the plan line it contradicts.
- Do not stage or commit.

Reply with this block last. `files` maps each changed path, relative to the repo, to its changed line count.
```workflow-result
{schema}
```
