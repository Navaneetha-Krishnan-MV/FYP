from fastapi import APIRouter, HTTPException, BackgroundTasks
from app.schemas import IndexRepositoryRequest, IndexRepositoryResponse, AnalyzeBugRequest
from app.indexing.pipeline import run_indexing_pipeline
from app.indexing.embedder import CodeEmbedder
from app.analysis.pipeline import run_agtr_analysis_pipeline
from app.config import settings

router = APIRouter()

@router.get("/health")
def health_check():
    return {
        "status": "online",
        "service": "CodeLens AI FastAPI Analysis Microservice",
        "embedding_model": settings.EMBEDDING_MODEL_NAME,
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

@router.post("/analyze-bug")
def analyze_bug(request: AnalyzeBugRequest, background_tasks: BackgroundTasks):
    if not request.bug_report_id:
        raise HTTPException(status_code=400, detail="bug_report_id is required")

    # Launch AGTR bug analysis pipeline task
    background_tasks.add_task(
        run_agtr_analysis_pipeline,
        bug_report_id=request.bug_report_id
    )

    return {
        "status": "processing",
        "bug_report_id": request.bug_report_id,
        "message": "AGTR bug analysis pipeline started in background"
    }
