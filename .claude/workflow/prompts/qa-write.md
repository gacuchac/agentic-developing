wf-step: {step_id}
Run folder: {run}
Agent: qa
Step: write
Repo: {repo}

Write the failing tests for this unit, and nothing else.

{unit}

Rules:
- Work only inside the repo above. Run tests from it with `.venv/bin/python -m pytest -q` when it has a `.venv`, else `python3 -m pytest -q`.
- Every test you add must fail now, before the code exists, and for the expected reason. Leave out a case that already passes, and list each one in `left_out`.
- Follow the unit's file and naming lines, and import the code the way the repo's existing tests do.
- Before you finish, `ruff check --config ~/Developing/ruff.toml <your test files>` must pass.
- Do not create or edit source files. Do not stage or commit.

Reply with only this block. `tests_added` lists the test files you added or changed. `red_run.failed` lists the full id of every new failing test, as `<file>::<name>`. `left_out` has one line per planned case you did not write because it already passes before the code, as `<case>: <why it passes today>`; use `[]` when there is none.
```workflow-result
{schema}
```
