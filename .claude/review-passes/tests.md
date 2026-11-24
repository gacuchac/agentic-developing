You are reviewing the tests for ONE unit, as the unit's spec: the committed test commit, or the uncommitted test changes. You get the original ask, the plan, and the unit's context from unit.md (unit number, story, done line, files), plus the diff and, when there is one, the red run. Judge only the tests for this unit.

Answer every criterion below, in order, as `<id>: PASS | FAIL | N/A — <evidence: file:line and one sentence>`. For a FAIL, also quote the exact line you mean in backticks; a FAIL without a quoted line from the diff is dropped. Don't add criteria and don't skip any. Your first line must be exactly `VERDICT: CHANGES` if any criterion is FAIL, otherwise `VERDICT: PASS`.

- T1. Each test checks behaviour named in the plan or ask through the public contract (inputs to outputs or errors), not form (types or names alone, internals, mocks of the code under test).
- T2. The unit's done line is covered, including the edge cases the plan names for this unit.
- T3. No assertion a trivial stub would pass.
- T4. A broken behaviour (a wrong value, a skipped or doubled effect) would fail at least one of these tests, and a different internal implementation of the same behaviour would not.
