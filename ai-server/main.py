from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from uvicorn import run
from app.api.routes import router as api_router
from app.config import settings
from app.logging_config import configure_logging

configure_logging()

app = FastAPI(
    title="CodeLens AI Service",
    description="Multi-stage AGTR Retrieval and Ranking Engine for Automated Bug Localization",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")

@app.get("/")
def read_root():
    return {
        "service": "CodeLens AI FastAPI Analysis Microservice",
        "docs": "/docs",
        "health": "/api/health"
    }

if __name__ == "__main__":
    run("main:app", host="0.0.0.0", port=settings.PORT, reload=True)
