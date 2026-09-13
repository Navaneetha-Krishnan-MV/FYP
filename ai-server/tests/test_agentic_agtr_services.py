"""Opt-in real PostgreSQL/pgvector + Neo4j integration; model responses are scripted."""
import json
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.analysis import agentic_pipeline
from app.database import Neo4jManager, get_db_connection
from app.indexing.embedder import CodeEmbedder
from app.repositories import indexes
from app.worker import process_one

pytestmark = pytest.mark.skipif(os.environ.get("RUN_AGTR_SERVICES") != "1", reason="Set RUN_AGTR_SERVICES=1 for DB/graph integration")


def test_worker_persists_all_agtr_signals_before_reasoning(monkeypatch):
    uid, pid, other_pid, bid, aid, *cids = [str(uuid.uuid4()) for _ in range(9)]
    now = datetime.now(timezone.utc)
    fingerprint = {"provider": "fixture", "model": "deterministic", "dimension": 768}
    monkeypatch.setattr(indexes, "embedding_fingerprint", lambda: fingerprint)
    monkeypatch.setattr(CodeEmbedder, "embed_text", lambda _: [1.0] + [0.0] * 767)
    conn = get_db_connection()
    conn.autocommit = True
    reason_calls = []

    class Gateway:
        def __init__(self, budget, guard):
            self.budget = budget

        def generate(self, role, payload, schema):
            self.budget.take("llm")
            if role == "understand":
                data = {"summary": "expired session remains valid", "search_terms": ["expired"]}
            elif role in {"code", "git", "dependency"}:
                data = {"response": {"action": "finish", "result": {"summary": "Inspect expiry comparison", "evidence_ids": []}}}
            elif role == "reason":
                # Read through a separate connection: the ranking must already be committed.
                with conn.cursor() as cur:
                    cur.execute('SELECT "finalRanking", "agtrWeights", "evidenceContext" FROM "AnalysisResult" WHERE id=%s', (aid,))
                    ranking, weights, context = cur.fetchone()
                assert ranking
                assert all(weights[name] > 0 for name in ("ws", "wg", "wt"))
                assert context["stage"] == "reason"
                assert [c["chunkId"] for c in ranking] == [c["chunk_id"] for c in payload["candidates"]]
                assert cids[3] not in {c["chunkId"] for c in ranking}
                reason_calls.append(ranking)
                evidence = [e["id"] for e in payload["evidence"] if e["kind"] == "code" and e["chunk_id"] == cids[0]]
                data = {"hypotheses": [{"candidate_id": cids[0], "mechanism": "Expiry comparison is inverted",
                        "suggested_fix": "Use now >= expiry", "evidence_ids": evidence,
                        "ranking_rationale": "Its source contains the inverted comparison that explains the symptoms."}]}
            else:
                evidence = [e["id"] for e in payload["evidence"] if e["kind"] == "code" and e["chunk_id"] == cids[0]]
                data = {"verdict": "supported", "primary_candidate_id": cids[0], "evidence_ids": evidence,
                        "explanation": "The cited comparison explains both observations"}
            return schema.model_validate(data)

    monkeypatch.setattr(agentic_pipeline, "ModelGateway", Gateway)
    try:
        with conn.cursor() as cur:
            cur.execute('INSERT INTO "User" (id,email,name,"updatedAt") VALUES (%s,%s,%s,NOW())', (uid, uid + "@fixture.invalid", "AGTR fixture"))
            for project_id in (pid, other_pid):
                cur.execute('''INSERT INTO "Project" (id,name,"localPath",languages,"userId",status,"updatedAt")
                    VALUES (%s,'AGTR fixture','',ARRAY['python'],%s,'READY',NOW())''', (project_id, uid))
            indexes.save_index(conn, pid, "fixture-generation", fingerprint, "current-revision", True, "")
            for i, cid in enumerate(cids):
                vector = [(.8, .7, .6, 1)[i], (.6, .714142842, .8, 0)[i]] + [0.0] * 766
                cur.execute('''INSERT INTO "CodeChunk" (id,"projectId","filePath",language,"chunkType",
                    "functionName","codeContent","startLine","endLine",imports,calls,embedding)
                    VALUES (%s,%s,'session.py','python','function',%s,%s,%s,%s,ARRAY[]::text[],ARRAY[]::text[],%s::vector)''',
                    (cid, other_pid if i == 3 else pid, "expired" if i == 0 else f"helper_{i}",
                     "def expired(now, expiry):\n    return now < expiry" if i == 0 else f"def helper_{i}():\n    return True", i * 10 + 1, i * 10 + 2, str(vector)))
            for revision, date in (("current-revision", now - timedelta(days=1)), ("future-commit", now + timedelta(days=1))):
                commit_id = str(uuid.uuid4())
                cur.execute('''INSERT INTO "Commit" (id,"projectId","commitHash","authorName","authorEmail",message,"committedAt")
                    VALUES (%s,%s,%s,'fixture','fixture@fixture.invalid','expired check',%s)''', (commit_id, pid, revision, date))
                cur.execute('''INSERT INTO "CommitChange" (id,"commitId","filePath","changeType",diff)
                    VALUES (%s,%s,'session.py','modified','@@ -1,2 +1,2 @@\n-old\n+new')''', (str(uuid.uuid4()), commit_id))
            cur.execute('''INSERT INTO "BugReport" (id,title,description,"projectId","userId")
                VALUES (%s,'Session expired','Expiry check is inverted',%s,%s)''', (bid, pid, uid))
            cur.execute('''INSERT INTO "AnalysisResult" (id,"bugReportId","projectId","userId","evidenceContext")
                VALUES (%s,%s,%s,%s,%s::json)''', (aid, bid, pid, uid, json.dumps({"engine": "agentic"})))
        Neo4jManager.execute_cypher('''CREATE (a:Function {projectId:$project, chunkId:$a}),
            (b:Function {projectId:$project, chunkId:$b}), (c:Function {projectId:$project, chunkId:$c}),
            (d:Function {projectId:$other, chunkId:$d}), (a)-[:CALLS]->(b), (b)-[:CALLS]->(c), (a)-[:CALLS]->(d)''',
            {"project": pid, "other": other_pid, **dict(zip("abcd", cids))})
        assert process_one(analysis_id=aid)
        assert not process_one(analysis_id=aid)
        with conn.cursor() as cur:
            cur.execute('''SELECT status,"semanticScores","graphScores","gitScores","finalRanking",
                "agtrWeights","evidenceContext","confidenceValue" FROM "AnalysisResult" WHERE id=%s''', (aid,))
            status, semantic, graph, git, ranking, weights, context, confidence = cur.fetchone()
        assert status == "completed", context.get("error")
        assert context["variant"] == "agent-agtr"
        assert context["report"]["outcome"] == "supported_hypothesis"
        assert confidence is None
        assert reason_calls == [ranking]
        assert weights == context["ranking_history"][-1]["agtr_weights"]
        assert all({c["chunkId"] for c in scores} == set(cids[:3]) for scores in (semantic, graph, git, ranking))
        assert all(context["signal_availability"].values())
        assert all(e.get("commit_hash") != "future-commit" for e in context["evidence"])
        assert all(c["hash"] != "future-c" for c in context["git_commits"])
        assert [p["phase"] for p in context["phase_outputs"]] == ["understand", "investigate", "rank", "reason", "verify", "finalize"]
    finally:
        with conn.cursor() as cur:
            cur.execute('DELETE FROM "Project" WHERE id=ANY(%s)', ([pid, other_pid],))
            cur.execute('DELETE FROM "User" WHERE id=%s', (uid,))
        conn.close()
        Neo4jManager.execute_cypher("MATCH (n) WHERE n.projectId IN $projects DETACH DELETE n", {"projects": [pid, other_pid]})
