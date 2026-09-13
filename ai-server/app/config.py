from pathlib import Path
from typing import Literal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

AI_SERVER_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    REASONING_PROVIDER: Literal["cloud", "local"] = "cloud"
    EMBEDDING_PROVIDER: Literal["cloud", "local"] = "cloud"
    LOCAL_REASONING_MODEL: str = "llama3.2:3b"
    LOCAL_EMBEDDING_MODEL: str = "nomic-embed-text"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    LLM_TIMEOUT_SECONDS: float = Field(default=90, gt=0)
    LOCAL_LLM_TIMEOUT_SECONDS: float = Field(default=180, gt=0)
    LOCAL_JSON_SCHEMA: bool = True
    CLOUD_REASONING_REQUESTS_PER_MINUTE: int = Field(default=5, ge=1, le=10000)
    LLM_MAX_ATTEMPTS: int = Field(default=2, ge=1, le=3)
    LLM_MAX_OUTPUT_TOKENS: int = Field(default=4096, ge=128, le=8192)
    RCA_MAX_ROUNDS: int = Field(default=3, ge=1, le=5)
    RCA_MAX_LLM_CALLS: int = Field(default=24, ge=4, le=100)
    RCA_MAX_TOOL_CALLS: int = Field(default=30, ge=1, le=100)
    RCA_MAX_ROLE_STEPS: int = Field(default=4, ge=1, le=8)
    RCA_MAX_SECONDS: float = Field(default=600, gt=0)
    RCA_MAX_CONTEXT_CHARS: int = Field(default=18000, ge=6000, le=48000)
    RCA_JOB_MAX_ATTEMPTS: int = Field(default=2, ge=1, le=5)
    JOB_POLL_SECONDS: float = Field(default=2, ge=0.2)
    REPOSITORIES_DIR: Path = AI_SERVER_DIR / "data" / "repositories"
    DATABASE_URL: str = "postgresql://postgres:navan@localhost:5433/codelens"
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "navan123"
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL_NAME: str = "gemini-3.6-flash"
    EMBEDDING_MODEL_NAME: str = "gemini-embedding-001"
    EMBEDDING_DIMENSION: int = Field(default=768, ge=768, le=768)
    EMBEDDING_BATCH_SIZE: int = Field(default=16, ge=1, le=100)
    # Batch calls reduce request count, while this process-wide cap spaces calls
    # from concurrent indexing jobs. Set it at or below the RPM shown for the
    # embedding model in Google AI Studio.
    EMBEDDING_REQUESTS_PER_MINUTE: int = Field(default=10, ge=1)
    EMBEDDING_MAX_ATTEMPTS: int = Field(default=5, ge=1, le=10)
    EMBEDDING_RETRY_BASE_SECONDS: float = 2.0
    EMBEDDING_RETRY_MAX_SECONDS: float = 60.0
    # gemini-embedding-001 caps each input at 2048 tokens; code tokenizes denser
    # than prose, so keep a conservative chars-per-token margin. The Gemini
    # Developer API (unlike Vertex) rejects inputs over the limit outright
    # rather than truncating, so this must stay comfortably under 2048 tokens.
    EMBEDDING_MAX_CHARS: int = Field(default=6000, ge=100, le=12000)
    # Ranked shortlist for either reasoning provider; source reads remain bounded.
    AGTR_LLM_CANDIDATES: int = Field(default=10, ge=1, le=20)
    AGTR_MAX_CANDIDATES: int = Field(default=40, ge=20, le=100)
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/ai-server.log"
    PORT: int = 8000

    # Resolve .env relative to ai-server, not the shell's current directory.
    model_config = SettingsConfigDict(
        env_file=AI_SERVER_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

settings = Settings()
