from langgraph.graph import StateGraph, START, END

from app.agents.budgets import BudgetExceeded
from app.agents.contracts import BugSignals, Hypotheses, Verification
from app.agents.runner import run_role
from app.agents.state import InvestigationState
from app.config import settings
from app.llm.structured_output import ModelOutputError


def build_investigation(gateway, tools, progress=lambda stage, details: None):
    """Sequential MVP graph. Python owns routing, stopping and final validation."""

    def _append_phase(state, phase):
        """Append a phase output dict to the accumulator."""
        existing = list(state.get("phase_outputs") or [])
        existing.append(phase)
        return existing

    def understand(state):
        progress("understand", {})
        signals = gateway.generate("understand", {"bug": state["bug"]}, BugSignals)
        phase = {
            "phase": "understand", "status": "completed",
            "summary": signals.summary,
            "search_terms": signals.search_terms,
            "missing_information": signals.missing_information,
        }
        progress("understand", {"output": phase})
        return {"signals": signals.model_dump(), "round": 0, "findings": [], "hypotheses": [],
                "tasks": [{"role": "code", "question": signals.summary + " Search terms: " + ", ".join(signals.search_terms)}],
                "phase_outputs": _append_phase(state, phase)}

    def investigate(state):
        round_number = state["round"] + 1
        progress("investigate", {"round": round_number})
        before = len(tools.evidence)
        findings = []
        all_traces = []
        # First-pass lexical seeds make small models useful even if search planning is weak.
        if round_number == 1:
            for term in state["signals"]["search_terms"][:2]:
                tools.execute("code", "keyword_search", {"query": term, "limit": 4})
            tools.execute("code", "semantic_search", {"query": state["signals"]["summary"], "limit": 5})
        for task in state["tasks"]:
            finding, trace = run_role(task["role"], task["question"], gateway, tools)
            findings.append({"role": task["role"], **finding.model_dump()})
            all_traces.append({"role": task["role"], "question": task["question"], "trace": trace})
        # A minimum inspected-code packet is required even if a role finishes early.
        if round_number == 1:
            for cid in list(tools.candidates)[:3]:
                if not any(e.get("chunk_id") == cid and e["kind"] == "code" for e in tools.evidence.values()):
                    tools.execute("code", "read_code", {"chunk_id": cid})
            if tools.candidates:
                cid = next(iter(tools.candidates))
                if tools.repository.index["has_git"]:
                    tools.execute("git", "git_history", {"chunk_id": cid, "limit": 2})
                    finding, trace = run_role("git", "Inspect relevant changes for: " + state["signals"]["summary"], gateway, tools)
                    findings.append({"role": "git", **finding.model_dump()})
                    all_traces.append({"role": "git", "question": "Inspect relevant changes", "trace": trace})
                tools.execute("dependency", "dependency_neighbors", {"chunk_id": cid})
                finding, trace = run_role("dependency", "Inspect the callers/callees that could explain: " + state["signals"]["summary"], gateway, tools)
                findings.append({"role": "dependency", **finding.model_dump()})
                all_traces.append({"role": "dependency", "question": "Inspect callers/callees", "trace": trace})
        phase = {
            "phase": "investigate", "status": "completed", "round": round_number,
            "findings": [{"role": f["role"], "summary": f["summary"], "evidence_ids": f.get("evidence_ids", [])} for f in findings],
            "agent_traces": all_traces,
            "new_evidence_count": len(tools.evidence) - before,
        }
        progress("investigate", {"round": round_number, "output": phase})
        return {"round": round_number, "findings": findings, "evidence_count_before": before,
                "phase_outputs": _append_phase(state, phase)}

    def reason(state):
        progress("reason", {"round": state["round"]})
        packet = tools.packet()
        if not any(e["kind"] == "code" for e in packet["evidence"]):
            phase = {"phase": "reason", "status": "completed", "round": state["round"],
                     "decision": "skipped", "reason": "no_code_evidence", "hypotheses": []}
            return {"hypotheses": [], "stop_reason": "no_code_evidence",
                    "phase_outputs": _append_phase(state, phase)}
        result = gateway.generate("reason", {"bug": state["bug"], **packet}, Hypotheses)
        visible_ids = {e["id"] for e in packet["evidence"]}
        # Validate source ownership and supporting code before any hypothesis is accepted.
        for hypothesis in result.hypotheses:
            tools.validate_refs(hypothesis.evidence_ids + hypothesis.counterevidence_ids)
            if not set(hypothesis.evidence_ids + hypothesis.counterevidence_ids) <= visible_ids:
                raise ModelOutputError("Hypothesis cited evidence outside its supplied context")
            if hypothesis.candidate_id not in tools.candidates or not tools.has_code(hypothesis.candidate_id, hypothesis.evidence_ids):
                raise ModelOutputError("Hypothesis lacks cited code evidence for its candidate")
        phase = {
            "phase": "reason", "status": "completed", "round": state["round"],
            "decision": "generated_hypotheses",
            "hypotheses": [{"candidate_id": h.candidate_id, "mechanism": h.mechanism,
                            "suggested_fix": h.suggested_fix, "evidence_ids": h.evidence_ids,
                            "counterevidence_ids": h.counterevidence_ids,
                            "assumptions": h.assumptions} for h in result.hypotheses],
            "missing_information": result.missing_information,
        }
        progress("reason", {"round": state["round"], "output": phase})
        return {"hypotheses": [h.model_dump() for h in result.hypotheses],
                "phase_outputs": _append_phase(state, phase)}

    def verify(state):
        progress("verify", {"round": state["round"]})
        if not state["hypotheses"]:
            verdict_data = {"verdict": "insufficient_evidence", "primary_candidate_id": None,
                    "evidence_ids": [], "explanation": "No defensible source-backed hypothesis was produced.",
                    "follow_up": [], "limitations": ["Insufficient causal evidence"]}
            phase = {"phase": "verify", "status": "completed", "round": state["round"],
                     "decision": "no_hypotheses", "verdict": "insufficient_evidence"}
            return {"verification": verdict_data, "phase_outputs": _append_phase(state, phase)}
        packet = tools.packet(required_ids=[eid for h in state["hypotheses"] for eid in h["evidence_ids"] + h["counterevidence_ids"]])
        result = gateway.generate("verify", {"bug": state["bug"], "hypotheses": state["hypotheses"], **packet}, Verification)
        tools.validate_refs(result.evidence_ids)
        if not set(result.evidence_ids) <= {e["id"] for e in packet["evidence"]}:
            raise ModelOutputError("Verifier cited evidence outside its supplied context")
        if result.verdict == "supported":
            hypothesis = next((h for h in state["hypotheses"] if h["candidate_id"] == result.primary_candidate_id), None)
            if not hypothesis or not tools.has_code(result.primary_candidate_id, result.evidence_ids):
                raise ModelOutputError("Verifier selected an unsupported candidate or citation")
        phase = {
            "phase": "verify", "status": "completed", "round": state["round"],
            "decision": result.verdict,
            "verdict": result.verdict,
            "primary_candidate_id": result.primary_candidate_id,
            "explanation": result.explanation,
            "evidence_ids": result.evidence_ids,
            "follow_up": [{"role": f.role, "question": f.question} for f in result.follow_up],
            "limitations": result.limitations,
        }
        progress("verify", {"round": state["round"], "output": phase})
        return {"verification": result.model_dump(), "phase_outputs": _append_phase(state, phase)}

    def route(state):
        result = state["verification"]
        if (result["verdict"] != "supported" and result["follow_up"]
                and state["round"] < settings.RCA_MAX_ROUNDS
                and len(tools.evidence) > state["evidence_count_before"]):
            return "replan"
        return "finalize"

    def replan(state):
        follow_up = state["verification"]["follow_up"]
        phase = {
            "phase": "replan", "status": "completed", "round": state["round"],
            "decision": "scheduling_follow_up",
            "tasks": follow_up,
        }
        progress("replan", {"output": phase})
        return {"tasks": follow_up, "phase_outputs": _append_phase(state, phase)}

    def finalize(state):
        verification = state.get("verification", {})
        supported = verification.get("verdict") == "supported"
        primary = next((h for h in state.get("hypotheses", []) if h["candidate_id"] == verification.get("primary_candidate_id")), None) if supported else None
        reason = state.get("stop_reason") or ("sufficient_evidence" if supported else
                 "round_limit" if state.get("round", 0) >= settings.RCA_MAX_ROUNDS else
                 "no_progress" if state.get("round", 0) > 1 and len(tools.evidence) == state.get("evidence_count_before") else "insufficient_evidence")
        report = {
            "outcome": "supported_hypothesis" if supported else "inconclusive",
            "primary_hypothesis": primary, "hypotheses": state.get("hypotheses", []),
            "verification": verification, "support_level": "supported" if supported else "insufficient",
            "runtime_verified": False, "termination_reason": reason, "rounds_used": state.get("round", 0),
            "limitations": list(dict.fromkeys(["Static analysis only; tests were not executed."] + verification.get("limitations", []))),
        }
        phase = {
            "phase": "finalize", "status": "completed",
            "decision": report["outcome"],
            "termination_reason": reason,
            "rounds_used": report["rounds_used"],
        }
        return {"report": report, "phase_outputs": _append_phase(state, phase)}

    def bounded(node):
        def call(state):
            try:
                return node(state)
            except BudgetExceeded:
                return {"stop_reason": "budget_exhausted", "verification": {}}
        return call

    def continue_or_finish(target):
        return lambda state: "finalize" if state.get("stop_reason") == "budget_exhausted" else target

    builder = StateGraph(InvestigationState)
    for name, node in {"understand": understand, "investigate": investigate, "reason": reason,
                       "verify": verify, "replan": replan, "finalize": finalize}.items():
        builder.add_node(name, bounded(node))
    builder.add_edge(START, "understand")
    builder.add_conditional_edges("understand", continue_or_finish("investigate"))
    builder.add_conditional_edges("investigate", continue_or_finish("reason"))
    builder.add_conditional_edges("reason", continue_or_finish("verify"))
    builder.add_conditional_edges("verify", lambda state: "finalize" if state.get("stop_reason") == "budget_exhausted" else route(state))
    builder.add_edge("replan", "investigate")
    builder.add_edge("finalize", END)
    return builder.compile()

