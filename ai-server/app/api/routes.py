from fastapi import APIRouter, HTTPException, BackgroundTasks
from app.schemas import IndexRepositoryRequest, IndexRepositoryResponse, AnalyzeBugRequest
from app.indexing.pipeline import run_indexing_pipeline
from app.indexing.embedder import CodeEmbedder
from app.database import get_db_connection
from app.llm.factory import reasoning_profile
from app.config import settings

router = APIRouter()

@router.get("/health")
def health_check():
    return {
        "status": "online",
        "service": "CodeLens AI FastAPI Analysis Microservice",
        "reasoning": reasoning_profile(),
        "embedding_provider": settings.EMBEDDING_PROVIDER,
        "embedding_model": settings.LOCAL_EMBEDDING_MODEL if settings.EMBEDDING_PROVIDER == "local" else settings.EMBEDDING_MODEL_NAME,
        "embedding_dimension": settings.EMBEDDING_DIMENSION,
    }


@router.get("/health/embedding")
def embedding_health_check():
    try:
        return CodeEmbedder.validate_environment()
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "ready": False,
                "model": settings.EMBEDDING_MODEL_NAME,
                "exception_type": type(exc).__name__,
                "reason": str(exc) or repr(exc),
            },
        ) from exc


@router.post("/index-repository", response_model=IndexRepositoryResponse)
def index_repository(request: IndexRepositoryRequest, background_tasks: BackgroundTasks):
    if not request.repo_url and not request.zip_path:
        raise HTTPException(status_code=400, detail="Either repo_url or zip_path is required")

    # Queue background indexing task
    background_tasks.add_task(
        run_indexing_pipeline,
        project_id=request.project_id,
        repo_url=request.repo_url,
        zip_path=request.zip_path
    )

    return IndexRepositoryResponse(
        project_id=request.project_id,
        status="PENDING",
        file_count=0,
        chunk_count=0,
        commit_count=0,
        message="Repository indexing pipeline started in background"
    )

@router.post("/analyze-bug", status_code=202)
def analyze_bug(request: AnalyzeBugRequest):
    # Compatibility endpoint: enqueue the exact existing row, idempotently.
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('''UPDATE "AnalysisResult" SET "evidenceContext"=
                json_build_object('engine','agentic','schema_version',1,'stage','queued')
                WHERE id=%s AND "bugReportId"=%s AND status='pending'
                AND "evidenceContext"->>'engine' IS DISTINCT FROM 'agentic'
                RETURNING id''', (request.analysis_id, request.bug_report_id))
            cur.execute('SELECT status FROM "AnalysisResult" WHERE id=%s AND "bugReportId"=%s',
                        (request.analysis_id, request.bug_report_id))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Analysis/bug association not found")
        conn.commit()
        return {"status": row[0], "analysis_id": request.analysis_id, "message": "Run the Python worker to process queued analyses."}
    finally:
        conn.close()
