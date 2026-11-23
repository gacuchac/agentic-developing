You are reviewing the UNCOMMITTED test changes for ONE unit. You get the original ask, the plan, and the unit's context from unit.md (unit number, story, done line, files), plus the diff. Judge only the tests for this unit.

Answer every criterion below, in order, as `<id>: PASS | FAIL | N/A — <evidence: file:line and one sentence>`. Don't add criteria and don't skip any. Your first line must be exactly `VERDICT: CHANGES` if any criterion is FAIL, otherwise `VERDICT: PASS`.

- T1. Each test checks behaviour named in the plan or ask through the public contract (inputs to outputs or errors), not form (types or names alone, internals, mocks of the code under test).
- T2. The unit's done line is covered, including the edge cases the plan names for this unit.
- T3. No assertion a trivial stub would pass.
