import time
import json
import traceback
from typing import Dict, Any
from app.config import settings
from app.database import get_db_connection
from app.llm.gemini_client import GeminiClient
from app.analysis.semantic_search import search_semantic_candidates
from app.analysis.agtr import (
    compute_confidence_gap,
    compute_zscore_gap,
    calculate_agtr_weights_adaptive,
    determine_adaptive_hops,
    rank_candidates_agtr
)
from app.analysis.graph_expander import expand_graph_neighbors
from app.analysis.git_scorer import compute_git_temporal_scores

def run_agtr_analysis_pipeline(bug_report_id: str) -> Dict[str, Any]:
    start_time = time.time()
    print(f"⚡ Starting AGTR bug analysis pipeline for bug: {bug_report_id}")

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Fetch BugReport details
        cursor.execute(
            'SELECT "id", "projectId", "title", "description", "severity" FROM "BugReport" WHERE "id" = %s;',
            (bug_report_id,)
        )
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Bug report {bug_report_id} not found")

        bug_id, project_id, title, description, severity = row

        # Check existing pending analysis record or create one
        cursor.execute(
            'SELECT "id" FROM "AnalysisResult" WHERE "bugReportId" = %s AND "status" = \'pending\' ORDER BY "createdAt" DESC LIMIT 1;',
            (bug_id,)
        )
        analysis_row = cursor.fetchone()
        if analysis_row:
            analysis_id = analysis_row[0]
            cursor.execute(
                'UPDATE "AnalysisResult" SET "status" = \'processing\' WHERE "id" = %s;',
                (analysis_id,)
            )
        else:
            cursor.execute(
                """
                INSERT INTO "AnalysisResult" (
                    "id", "bugReportId", "projectId", "userId", "status"
                ) VALUES (
                    gen_random_uuid()::text, %s, %s,
                    (SELECT "userId" FROM "BugReport" WHERE "id" = %s),
                    'processing'
                ) RETURNING "id";
                """,
                (bug_id, project_id, bug_id)
            )
            analysis_id = cursor.fetchone()[0]

        conn.commit()

        # Step 1: Bug Query Processing & Expansion
        query_data = GeminiClient.generate_query_expansion(title, description)
        search_query = query_data.get("expanded_query", f"{title} {description}")
        search_terms = query_data.get("search_terms", [title])

        # Step 2: Semantic Retrieval in pgvector
        semantic_seeds = search_semantic_candidates(project_id, search_query, top_k=15)

        # Step 3 (AGTR Step 1): Measure semantic confidence gap Cs
        Cs = compute_confidence_gap([c.get("semantic_score", 0.0) for c in semantic_seeds])

        # Step 4 (AGTR Step 2): Adaptive Hop Expansion (semantic confidence only)
        hops = determine_adaptive_hops(Cs)
        expanded_candidates, dependency_paths = expand_graph_neighbors(
            project_id, semantic_seeds, hops=hops, lambda_decay=0.5
        )

        # Step 5 (AGTR Step 3): Git Temporal Decay Scoring
        scored_candidates, git_commits = compute_git_temporal_scores(
            project_id, expanded_candidates, search_terms, mu_decay=0.05
        )

        # Step 6: Measure per-signal confidence via z-score gap (top1 vs
        # rest, in units of that signal's own spread) now that graph and
        # temporal scores both exist. Min-max-then-gap looked comparable
        # across signals but wasn't: PageRank on a small graph is
        # naturally power-law-shaped (a hub or two far ahead of a long
        # tail) while semantic cosine similarity clusters tightly, so a
        # min-max gap made the graph signal look "confident" almost
        # regardless of query. The z-score gap is far less sensitive to
        # that shape difference. Semantic uses its own z-score gap here
        # too (Cs above stays min-max/raw - unchanged - for the
        # confidence_label UI badge and hop-depth selection only).
        Cs_z = compute_zscore_gap([c.get("semantic_score", 0.0) for c in semantic_seeds])
        Cg_z = compute_zscore_gap([c.get("graph_score", 0.0) for c in scored_candidates])
        Ct_z = compute_zscore_gap([c.get("git_score", 0.0) for c in scored_candidates])
        ws, wg, wt = calculate_agtr_weights_adaptive(Cs_z, Cg_z, Ct_z)

        # Step 7 (AGTR Step 4): Final Candidate AGTR Ranking
        final_ranked = rank_candidates_agtr(scored_candidates, ws, wg, wt)

        # Determine confidence level label - semantic confidence only,
        # unchanged thresholds/behavior from before this redesign.
        if Cs > 0.30:
            confidence_label = "HIGH"
            confidence_val = min(0.95, 0.70 + Cs)
        elif Cs > 0.15:
            confidence_label = "MEDIUM"
            confidence_val = min(0.85, 0.50 + Cs)
        else:
            confidence_label = "LOW"
            confidence_val = max(0.35, 0.20 + Cs)

        # Top evidence package for RAG
        top_candidates = final_ranked[:settings.AGTR_LLM_CANDIDATES]
        evidence_context = {
            "top_candidates": top_candidates,
            "dependency_paths": dependency_paths,
            "git_commits": git_commits,
            "confidence_level": confidence_label,
            "agtr_weights": {"ws": ws, "wg": wg, "wt": wt},
            "confidence_gap_C": Cs
        }

        # Step 7: Grounded RAG & Gemini Reasoning
        llm_output = GeminiClient.generate_root_cause_analysis(title, description, evidence_context)

        processing_time_ms = int((time.time() - start_time) * 1000)

        # Serialize intermediate AGTR scores for UI transparency
        sem_scores_json = json.dumps([{"chunkId": c["chunk_id"], "score": c["semantic_score"]} for c in final_ranked])
        graph_scores_json = json.dumps([{"chunkId": c["chunk_id"], "score": c["graph_score"]} for c in final_ranked])
        git_scores_json = json.dumps([{"chunkId": c["chunk_id"], "score": c["git_score"]} for c in final_ranked])
        final_ranking_json = json.dumps([{
            "chunkId": c["chunk_id"],
            "functionName": c["function_name"],
            "filePath": c["file_path"],
            "rank": c["rank"],
            "agtrScore": c["agtr_score"],
            "semanticScore": c["semantic_score"],
            "graphScore": c["graph_score"],
            "gitScore": c["git_score"]
        } for c in final_ranked])

        # Step 8: Save complete AnalysisResult to Postgres
        cursor.execute(
            """
            UPDATE "AnalysisResult"
            SET
                "status" = 'completed',
                "semanticScores" = %s::json,
                "graphScores" = %s::json,
                "gitScores" = %s::json,
                "finalRanking" = %s::json,
                "confidence" = %s::"ConfidenceLevel",
                "confidenceValue" = %s,
                "semanticGap" = %s,
                "agtrWeights" = %s::json,
                "hopsUsed" = %s,
                "rootCauseFile" = %s,
                "rootCauseFunction" = %s,
                "rootCauseCommit" = %s,
                "explanation" = %s,
                "suggestedFix" = %s,
                "dependencyPath" = %s,
                "evidenceContext" = %s::json,
                "processingTimeMs" = %s,
                "completedAt" = NOW()
            WHERE "id" = %s;
            """,
            (
                sem_scores_json,
                graph_scores_json,
                git_scores_json,
                final_ranking_json,
                confidence_label,
                confidence_val,
                Cs,
                json.dumps({"ws": ws, "wg": wg, "wt": wt}),
                hops,
                llm_output.get("root_cause_file"),
                llm_output.get("root_cause_function"),
                llm_output.get("root_cause_commit"),
                llm_output.get("explanation"),
                llm_output.get("suggested_fix"),
                llm_output.get("dependency_path_summary"),
                json.dumps(evidence_context),
                processing_time_ms,
                analysis_id
            )
        )
        conn.commit()

        print(f"✅ AGTR Analysis successfully completed for bug: {bug_id} in {processing_time_ms}ms")

        return {
            "analysis_id": analysis_id,
            "status": "completed",
            "confidence": confidence_label,
            "confidence_value": confidence_val,
            "semantic_gap": Cs,
            "agtr_weights": {"ws": ws, "wg": wg, "wt": wt},
            "root_cause_file": llm_output.get("root_cause_file"),
            "root_cause_function": llm_output.get("root_cause_function"),
            "root_cause_commit": llm_output.get("root_cause_commit"),
            "explanation": llm_output.get("explanation"),
            "suggested_fix": llm_output.get("suggested_fix"),
            "processing_time_ms": processing_time_ms
        }

    except Exception as e:
        conn.rollback()
        err_trace = traceback.format_exc()
        print(f"❌ AGTR analysis failed for bug {bug_report_id}:\n{err_trace}")
        try:
            cursor.execute(
                'UPDATE "AnalysisResult" SET "status" = \'failed\' WHERE "bugReportId" = %s AND "status" = \'processing\';',
                (bug_report_id,)
            )
            conn.commit()
        except:
            pass
        raise e
    finally:
        cursor.close()
        conn.close()
