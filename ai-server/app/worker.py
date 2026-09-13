"""Small durable DB queue. Interrupted MVP runs restart; no checkpoint claim."""
import logging
import time

from app.analysis.agentic_pipeline import run_agentic_analysis
from app.config import settings
from app.database import get_db_connection
from app.repositories.indexes import ProjectBusy, project_lock

logger = logging.getLogger(__name__)


def process_one(analysis_id: str | None = None) -> bool:
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            query = '''SELECT id, "projectId" FROM "AnalysisResult"
                WHERE status IN ('pending','processing') AND "evidenceContext"->>'engine'='agentic'
                '''
            if analysis_id is not None:
                query += ' AND id=%s'
            cur.execute(query + ' ORDER BY "createdAt" LIMIT 20', (analysis_id,) if analysis_id is not None else ())
            jobs = cur.fetchall()
    finally:
        conn.close()
    for analysis_id, project_id in jobs:
        try:
            with project_lock(project_id) as session:
                run_agentic_analysis(session, analysis_id)
                return True
        except ProjectBusy:
            continue
    return False


def main():
    from app.logging_config import configure_logging
    configure_logging()
    logger.info("agentic_worker_started reasoning=%s embeddings=%s", settings.REASONING_PROVIDER, settings.EMBEDDING_PROVIDER)
    while True:
        try:
            if not process_one():
                time.sleep(settings.JOB_POLL_SECONDS)
        except KeyboardInterrupt:
            return
        except Exception:
            logger.exception("worker_poll_failed")
            time.sleep(settings.JOB_POLL_SECONDS)
