wf-step: {step_id}
Run folder: {run}
Agent: qa
Step: fix
Repo: {repo}

Fix the tests of this unit for the finding or dispute named at the end of this prompt, or in the main session's launch message. Change only what that needs.

{unit}

Rules:
- Work only inside the repo above. Before starting, read the Approach and Contracts sections of the plan on the `Plan:` line: they hold decisions that apply to every unit. Run tests with the interpreter on the `Python:` line (`<Python> -m pytest -q`) in place of any `.venv` or `python3` rule.
- A test you add must fail against the code as committed; leave out a case that already passes. The implementer's uncommitted code may be in the working tree: judge red against the last commit, not against it.
- Before you finish, `ruff check --config ~/Developing/ruff.toml <your test files>` must pass.
- Do not edit source files. Do not stage or commit.

Reply with only this block. `tests_changed` lists the test files you changed.
```workflow-result
{schema}
```
