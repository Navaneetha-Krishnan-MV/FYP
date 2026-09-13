-- Additive, idempotent MVP migration. Apply with python -m app.cli setup.
-- Existing project data is preserved; legacy indexes require reindexing.
CREATE TABLE IF NOT EXISTS "RepositoryIndex" (
    "projectId" TEXT PRIMARY KEY REFERENCES "Project"("id") ON DELETE CASCADE,
    "generation" TEXT NOT NULL,
    "fingerprint" JSONB NOT NULL,
    "revision" TEXT NOT NULL,
    "hasGit" BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS "AnalysisResult_queue_idx" ON "AnalysisResult" ("status", "createdAt");
