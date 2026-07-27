from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

AI_SERVER_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://postgres:navan@localhost:5433/codelens"
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "navan123"
    GEMINI_API_KEY: str = ""
    EMBEDDING_MODEL_NAME: str = "gemini-embedding-001"
    EMBEDDING_DIMENSION: int = 768
    EMBEDDING_BATCH_SIZE: int = 16
    # gemini-embedding-001 caps each input at 2048 tokens; code tokenizes denser
    # than prose, so keep a conservative chars-per-token margin. The Gemini
    # Developer API (unlike Vertex) rejects inputs over the limit outright
    # rather than truncating, so this must stay comfortably under 2048 tokens.
    EMBEDDING_MAX_CHARS: int = 6000
    # How many AGTR-ranked candidates get their full code sent to Gemini for root
    # cause reasoning. Keep this matched to what the UI's "Ranked Candidates"
    # panel shows, so Gemini reasons over the same evidence the user can see.
    AGTR_LLM_CANDIDATES: int = 10
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
