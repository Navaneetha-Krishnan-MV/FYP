from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class IndexRepositoryRequest(BaseModel):
    project_id: str
    repo_url: Optional[str] = None
    zip_path: Optional[str] = None

class IndexRepositoryResponse(BaseModel):
    project_id: str
    status: str
    file_count: int
    chunk_count: int
    commit_count: int
    message: str

class AnalyzeBugRequest(BaseModel):
    bug_report_id: str
    analysis_id: str

class CandidateScore(BaseModel):
    chunk_id: str
    function_name: str
    file_path: str
    semantic_score: float
    graph_score: float
    git_score: float
    agtr_score: float

class AnalyzeBugResponse(BaseModel):
    analysis_id: str
    bug_report_id: str
    status: str
    confidence: str
    confidence_value: float
    semantic_gap: float
    root_cause_file: Optional[str]
    root_cause_function: Optional[str]
    root_cause_commit: Optional[str]
    explanation: Optional[str]
    suggested_fix: Optional[str]
    top_candidates: List[CandidateScore]
    processing_time_ms: int
