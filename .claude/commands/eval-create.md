---
description: Write eval cases for a task with me, one case at a time
argument-hint: <project>/<task-id>
disable-model-invocation: true
---

Read .claude/runs/$0/plan.md, especially the user stories and the Evals section. Ask me how many cases each flagged story needs.
Then draft one case at a time and go through it with me before saving it:
- id, story, persona (who the user is and how they talk), goal, opening_message,
- branches: how the user reacts to the agent's replies, as "if the agent ..., then the user ...". Include at least one branch for a clarifying question from the agent and one for the agent getting something wrong.
- stop_condition and max_turns,
- budgets: max_tool_calls, max_total_tokens, max_seconds,
- thresholds: the minimum score for tool_use, groundedness, answers_question and completeness (default 4).
Save each case I approve to .claude/runs/$0/evals/<case-id>.yaml, in the format of section 5b. Don't commit anything; the cases are copied to evals/cases/ and committed on the task's branch when it's built.
