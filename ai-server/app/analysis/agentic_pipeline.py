"""Run one exact analysis under a project lock and persist the evidence packet."""
import json
import logging
import time

from app.agents.budgets import Budget
from app.agents.graph import build_investigation
from app.analysis.agtr import rank_candidates_agtr
from app.config import settings
from app.llm.factory import reasoning_profile
from app.llm.structured_output import ModelGateway
from app.repositories.indexes import load_index
from app.tools.executor import ToolExecutor
from app.tools.repository import RepositoryTools

logger = logging.getLogger(__name__)


def run_agentic_analysis(conn, analysis_id: str):
    """The caller owns the project's session lock for the full call."""
    started = time.monotonic()
    with conn.cursor() as cur:
        cur.execute('''SELECT a."projectId", a."evidenceContext", b.title, b.description,
            b."stepsToReproduce", p.status FROM "AnalysisResult" a
            JOIN "BugReport" b ON b.id=a."bugReportId" JOIN "Project" p ON p.id=a."projectId"
            WHERE a.id=%s AND a.status IN ('pending','processing')''', (analysis_id,))
        row = cur.fetchone()
    if not row:
        return
    project_id, previous, title, description, steps, project_status = row
    context = {"engine": "agentic", "schema_version": 1, "stage": "starting", "events": [],
               "phase_outputs": [], "attempt": (previous or {}).get("attempt", 0) + 1, "reasoning": reasoning_profile()}
    tools = None
    budget = None

    def persist_context():
        with conn.cursor() as cur:
            cur.execute('UPDATE "AnalysisResult" SET "evidenceContext"=%s::json WHERE id=%s', (json.dumps(context, default=str), analysis_id))

    def guard():
        # The same non-reconnecting session owns the lock and every result write.
        with conn.cursor() as cur:
            cur.execute("SELECT 1")

    def progress(stage, details):
        context["stage"] = stage
        output = details.pop("output", None)
        context["events"].append({"stage": stage, **details})
        if output:
            context["phase_outputs"].append(output)
        persist_context()

    try:
        if context["attempt"] > settings.RCA_JOB_MAX_ATTEMPTS:
            raise RuntimeError("Worker restart attempt limit reached; submit a new analysis.")
        if project_status != "READY":
            raise RuntimeError("Project is not ready. Complete indexing before analysis.")
        index = load_index(conn, project_id)
        # A recovered run must never silently switch index generations or provider settings.
        if previous and previous.get("generation") and previous["generation"] != index["generation"]:
            raise RuntimeError("Index changed since the interrupted run; submit a new analysis.")
        if previous and previous.get("reasoning") and previous["reasoning"] != context["reasoning"]:
            raise RuntimeError("Reasoning configuration changed since this run; submit a new analysis.")
        context.update({"generation": index["generation"], "revision": index["revision"], "embedding": index["fingerprint"]})
        with conn.cursor() as cur:
            cur.execute('UPDATE "AnalysisResult" SET status=\'processing\' WHERE id=%s', (analysis_id,))
        progress("starting", {})
        budget = Budget()
        repo = RepositoryTools(conn, project_id, index)
        tools = ToolExecutor(repo, budget, guard)
        graph = build_investigation(ModelGateway(budget, guard), tools, progress)
        state = graph.invoke({"bug": {"title": title[:1000], "description": description[:5000], "steps": (steps or "")[:2000]}},
                             config={"recursion_limit": 40})
        report = state["report"]
        phase_outputs = state.get("phase_outputs") or context.get("phase_outputs", [])
        # The MVP keeps retrieval ordering separate from the causal verdict.
        candidates = list(tools.candidates.values())
        weights = {"ws": 1.0, "wg": 0.0, "wt": 0.0}
        ranked = rank_candidates_agtr(candidates, **weights)
        primary = report["primary_hypothesis"]
        location = tools.candidates.get(primary["candidate_id"], {}) if primary else {}
        context.update({"stage": "completed", "report": report, "evidence": list(tools.evidence.values()),
                        "tool_events": tools.events, "usage": budget.usage(),
                        "phase_outputs": phase_outputs,
                        "top_candidates": [{k: v for k, v in c.items() if k != "code_content"} for c in ranked],
                        "ranking_note": "Semantic relevance only in the MVP; Git and graph are inspected evidence, not calibrated confidence."})
        ranking = [{"chunkId": c["chunk_id"], "filePath": c["file_path"], "functionName": c["function_name"],
                    "rank": c["rank"], "agtrScore": c["agtr_score"], "semanticScore": c["semantic_score"],
                    "graphScore": c["graph_score"], "gitScore": c["git_score"]} for c in ranked]
        with conn.cursor() as cur:
            cur.execute('''UPDATE "AnalysisResult" SET status='completed', "confidence"=NULL,
                "confidenceValue"=NULL, "rootCauseFile"=%s, "rootCauseFunction"=%s,
                "rootCauseCommit"=NULL, explanation=%s, "suggestedFix"=%s,
                "evidenceContext"=%s::json, "finalRanking"=%s::json,
                "processingTimeMs"=%s, "completedAt"=NOW() WHERE id=%s''', (
                location.get("file_path"), location.get("function_name"),
                primary["mechanism"] if primary else report["verification"].get("explanation", "The investigation could not establish a root cause."),
                primary["suggested_fix"] if primary else None, json.dumps(context, default=str), json.dumps(ranking),
                int((time.monotonic() - started) * 1000), analysis_id))
    except Exception as exc:
        logger.exception("agentic_analysis_failed analysis_id=%s", analysis_id)
        # Known domain errors are safe. Unexpected infrastructure errors stay in logs.
        safe_error = str(exc)[:500] if isinstance(exc, (RuntimeError, ValueError)) else "Analysis service failed. See ai-server logs."
        context.update({"stage": "failed", "error": safe_error})
        if tools is not None:
            context.update({"evidence": list(tools.evidence.values()), "tool_events": tools.events})
        if budget is not None:
            context["usage"] = budget.usage()
        with conn.cursor() as cur:
            cur.execute('UPDATE "AnalysisResult" SET status=\'failed\', "evidenceContext"=%s::json, "completedAt"=NOW() WHERE id=%s',
                        (json.dumps(context, default=str), analysis_id))
