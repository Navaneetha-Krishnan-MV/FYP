from contextlib import contextmanager
import hashlib
import json

from app.database import get_db_connection
from app.embeddings.fingerprint import embedding_fingerprint, require_compatible


class ProjectBusy(RuntimeError):
    pass


def project_lock_key(project_id: str) -> int:
    return int.from_bytes(hashlib.sha256(("codelens:" + project_id).encode()).digest()[:8], "big", signed=True)


@contextmanager
def project_lock(project_id: str):
    """Session lock shared by indexing and analysis; no open long transaction."""
    conn = get_db_connection()
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_try_advisory_lock(%s)", (project_lock_key(project_id),))
            if not cur.fetchone()[0]:
                raise ProjectBusy("This project is being indexed or analyzed. Retry shortly.")
        yield conn
    finally:
        # Closing the owning session releases the advisory lock, even after errors.
        conn.close()


def load_index(conn, project_id: str, *, check_embedding=True) -> dict:
    with conn.cursor() as cur:
        cur.execute('SELECT "generation", "fingerprint", "revision", "hasGit" FROM "RepositoryIndex" WHERE "projectId" = %s', (project_id,))
        row = cur.fetchone()
        if not row:
            raise RuntimeError("REINDEX_REQUIRED: reindex this project to record embedding provenance.")
        index = dict(zip(("generation", "fingerprint", "revision", "has_git"), row))
        if check_embedding:
            require_compatible(index["fingerprint"], embedding_fingerprint())
        return index


def save_index(conn, project_id: str, generation: str, fingerprint: dict, revision: str, has_git: bool, path: str):
    with conn.cursor() as cur:
        cur.execute('''INSERT INTO "RepositoryIndex" ("projectId", "generation", "fingerprint", "revision", "hasGit")
            VALUES (%s, %s, %s::jsonb, %s, %s)
            ON CONFLICT ("projectId") DO UPDATE SET "generation"=EXCLUDED."generation",
            "fingerprint"=EXCLUDED."fingerprint", "revision"=EXCLUDED."revision", "hasGit"=EXCLUDED."hasGit"''',
            (project_id, generation, json.dumps(fingerprint), revision, has_git))
        cur.execute('UPDATE "Project" SET "localPath"=%s WHERE "id"=%s', (path, project_id))
