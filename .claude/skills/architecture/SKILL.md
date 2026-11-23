---
name: architecture
description: Use whenever a function's input or output contract must change, a task needs an architectural change, or a plan needs its solution or software architecture worked out. Proposes first and edits nothing until the user approves.
---

1. Write a proposal to the run folder as architecture.md: the old and new contract (or the proposed architecture), every caller or dependent found with Grep, the migration order, the risks, and how the tests must change.
2. Show me the proposal and stop. Do not edit code until I approve it in this conversation.
3. After I approve: apply the change and update every caller. You may hand clearly specified caller updates to the implementer subagent. Then have qa run the full suite and codex-reviewer run passes answers-ask and principles.
