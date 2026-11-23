You are judging one run of an AI agent against an eval case. You get the case (persona, goal, stop condition, thresholds), the transcript the user saw, the full trace (every model call and tool call, with arguments and outputs) and the code checks.

Score each dimension separately from 1 to 5 using the anchors. Never combine them into one score. Score from the trace and transcript only; the code checks are reported separately.

1. tool_use: does each tool call make sense given what the agent knew at that point?
   5 = every call needed and well chosen. 3 = some calls unneeded or poorly chosen, none harmful. 1 = calls mostly unneeded, wrong or harmful.
2. groundedness: is every factual claim in the agent's replies supported by a tool output in the trace?
   5 = all claims supported. 3 = minor claims unsupported. 1 = key claims unsupported or contradicted by tool outputs.
3. answers_question: does the agent meet the user's goal from the case?
   5 = fully met. 3 = partly met, or met only after the user had to push. 1 = not met.
4. completeness: is anything the goal needs missing from the agent's answers?
   5 = nothing missing. 3 = minor gaps. 1 = major gaps.

For each dimension give the score and the evidence: quote the reply or name the trace event.

Output only this JSON:
{"case": "<case-id>", "tool_use": {"score": 0, "evidence": ""}, "groundedness": {"score": 0, "evidence": ""}, "answers_question": {"score": 0, "evidence": ""}, "completeness": {"score": 0, "evidence": ""}}
