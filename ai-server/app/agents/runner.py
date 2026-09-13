import json

from app.agents.contracts import AgentAction, FinishAction, Finding
from app.config import settings


def run_role(role, question, gateway, tools):
    """An ordinary text/JSON model can request tools through this bounded loop.
    Returns (finding, tool_trace) where tool_trace records every agent step."""
    observation = None
    tool_trace = []
    seen_calls = set()
    for step in range(settings.RCA_MAX_ROLE_STEPS):
        packet = tools.packet()
        payload = {
            "question": question, "candidates": packet["candidates"],
            "tools": tools.catalog(role), "remaining_steps": settings.RCA_MAX_ROLE_STEPS - step,
            "observation": observation,
        }
        result = gateway.generate(role, payload, AgentAction).response
        if isinstance(result, FinishAction):
            tools.validate_refs(result.result.evidence_ids)
            tool_trace.append({"step": step, "action": "finish", "summary": result.result.summary,
                               "evidence_ids": result.result.evidence_ids})
            return result.result, tool_trace
        tool_trace.append({"step": step, "action": "tool", "tool": result.tool, "arguments": result.arguments})

        call_signature = (result.tool, json.dumps(result.arguments, sort_keys=True))
        if call_signature in seen_calls:
            return Finding(summary="Repeated check reused an existing observation; no new evidence was added.",
                           evidence_ids=observation.get("evidence_ids", []) if observation else []), tool_trace
        seen_calls.add(call_signature)

        observation = tools.execute(role, result.tool, result.arguments)
        tool_trace[-1]["status"] = observation.get("status", "unknown")
        tool_trace[-1]["evidence_ids"] = observation.get("evidence_ids", [])
    return Finding(summary="Role step limit reached; collected observations remain available.",
                   evidence_ids=(observation or {}).get("evidence_ids", [])), tool_trace

