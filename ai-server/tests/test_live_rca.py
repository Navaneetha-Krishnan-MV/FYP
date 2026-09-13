"""Opt-in real DB/Neo4j/model test. Creates and removes only its own fixture."""
import json
import os
import shutil
import uuid
import zipfile

import pytest

from app.config import settings
from app.database import get_db_connection, Neo4jManager
from app.indexing.pipeline import run_indexing_pipeline
from app.repositories.indexes import project_lock, ProjectBusy
from app.worker import process_one

pytestmark = pytest.mark.skipif(os.environ.get("RUN_LIVE_RCA") != "1", reason="Set RUN_LIVE_RCA=1 for real service/model tests")


def test_index_queue_tools_and_result_with_real_services(tmp_path):
    uid, pid, bid, aid = [str(uuid.uuid4()) for _ in range(4)]
    source = '''def is_expired(now, expires_at):
    """True means an existing session should be rejected."""
    return now < expires_at

def can_access(now, expires_at):
    return not is_expired(now, expires_at)
'''
    archive = tmp_path / "repo.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("session.py", source)
    conn = get_db_connection()
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute('INSERT INTO "User" (id,email,name,"updatedAt") VALUES (%s,%s,%s,NOW())', (uid, uid + "@fixture.invalid", "RCA test fixture"))
            cur.execute('''INSERT INTO "Project" (id,name,"localPath",languages,"userId","updatedAt")
                VALUES (%s,'RCA integration fixture','',ARRAY['python'],%s,NOW())''', (pid, uid))
            cur.execute('''INSERT INTO "BugReport" (id,title,description,"projectId","userId")
                VALUES (%s,'Session expiration is inverted',%s,%s,%s)''',
                (bid, "can_access(50, 100) returns False before expiry, but should be True. can_access(150, 100) returns True after expiry, but should be False.", pid, uid))
        run_indexing_pipeline(pid, zip_path=str(archive))
        with conn.cursor() as cur:
            cur.execute('SELECT status,"errorMsg" FROM "Project" WHERE id=%s', (pid,))
            status, error = cur.fetchone()
            assert status == "READY", error
        with project_lock(pid):
            with pytest.raises(ProjectBusy):
                with project_lock(pid):
                    pass
        with conn.cursor() as cur:
            cur.execute('''INSERT INTO "AnalysisResult" (id,"bugReportId","projectId","userId","evidenceContext")
                VALUES (%s,%s,%s,%s,%s::json)''', (aid, bid, pid, uid, json.dumps({"engine": "agentic"})))
        # Exercise the real queue without consuming other users' jobs.
        with project_lock(pid):
            assert not process_one(analysis_id=aid)
        assert process_one(analysis_id=aid)
        assert not process_one(analysis_id=aid)  # terminal rows cannot be claimed twice
        with conn.cursor() as cur:
            cur.execute('SELECT status,"rootCauseFunction","evidenceContext" FROM "AnalysisResult" WHERE id=%s', (aid,))
            status, function, context = cur.fetchone()
        assert status == "completed", context.get("error")
        assert context["report"]["outcome"] == "supported_hypothesis", context["report"]
        assert function == "is_expired"
        assert context["report"]["runtime_verified"] is False
        assert context["evidence"]
        assert context["usage"]["llm_calls"] <= settings.RCA_MAX_LLM_CALLS
        print(json.dumps({"provider": settings.REASONING_PROVIDER, "embeddings": settings.EMBEDDING_PROVIDER,
                          "outcome": context["report"]["outcome"], "function": function, "usage": context["usage"]}))
    finally:
        with conn.cursor() as cur:
            cur.execute('DELETE FROM "Project" WHERE id=%s', (pid,))
            cur.execute('DELETE FROM "User" WHERE id=%s', (uid,))
        conn.close()
        Neo4jManager.execute_cypher("MATCH (n {projectId: $project}) DETACH DELETE n", {"project": pid})
        shutil.rmtree(settings.REPOSITORIES_DIR / pid, ignore_errors=True)
