import os
import logging
import time
import uuid
from pathlib import Path
import hashlib
import git
from app.repositories.indexes import project_lock, save_index
from app.embeddings.fingerprint import embedding_fingerprint
from app.repositories.paths import allowed_source
from typing import Optional
from app.database import get_db_connection
from app.indexing.cloner import prepare_repository
from app.indexing.parser import parse_file
from app.indexing.embedder import CodeEmbedder, save_code_chunks_to_db
from app.indexing.graph_builder import build_neo4j_graph
from app.indexing.git_indexer import extract_and_save_git_history

logger = logging.getLogger(__name__)


def update_project_status(project_id: str, status: str, error_msg: Optional[str] = None, file_count: int = 0, chunk_count: int = 0, commit_count: int = 0, languages: list = None):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        if error_msg:
            cursor.execute(
                'UPDATE "Project" SET "status" = %s::"ProjectStatus", "errorMsg" = %s, "updatedAt" = NOW() WHERE "id" = %s;',
                (status, error_msg, project_id)
            )
        elif status == "READY":
            cursor.execute(
                """
                UPDATE "Project"
                SET "status" = %s::"ProjectStatus",
                    "fileCount" = %s,
                    "chunkCount" = %s,
                    "commitCount" = %s,
                    "languages" = %s,
                    "errorMsg" = NULL,
                    "updatedAt" = NOW()
                WHERE "id" = %s;
                """,
                (status, file_count, chunk_count, commit_count, languages or [], project_id)
            )
        else:
            cursor.execute(
                'UPDATE "Project" SET "status" = %s::"ProjectStatus", "updatedAt" = NOW() WHERE "id" = %s;',
                (status, project_id)
            )
        conn.commit()
        logger.info(
            "project_status_updated project_id=%s status=%s",
            project_id,
            status,
        )
    except Exception as e:
        conn.rollback()
        logger.exception(
            "project_status_update_failed project_id=%s requested_status=%s "
            "exception_type=%s reason=%s",
            project_id,
            status,
            type(e).__name__,
            str(e) or repr(e),
        )
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()

def run_indexing_pipeline(project_id: str, repo_url: Optional[str] = None, zip_path: Optional[str] = None):
    with project_lock(project_id) as lock_conn:
        return _run_indexing_locked(project_id, repo_url, zip_path, lock_conn)


def _run_indexing_locked(project_id, repo_url, zip_path, lock_conn):
    started_at = time.perf_counter()
    run_id = str(uuid.uuid4())
    stage = "STARTING"
    logger.info(
        "indexing_pipeline_started run_id=%s project_id=%s source_type=%s",
        run_id,
        project_id,
        "git" if repo_url else "zip",
    )

    try:
        fingerprint = embedding_fingerprint()
        # Step 1: Clone / Extract Repo
        stage = "CLONING"
        update_project_status(project_id, "CLONING")
        logger.info(
            "indexing_stage_started run_id=%s project_id=%s stage=%s",
            run_id,
            project_id,
            stage,
        )
        repo_dir, languages = prepare_repository(project_id, repo_url, zip_path)
        logger.info(
            "indexing_stage_completed run_id=%s project_id=%s stage=%s "
            "repo_dir=%s languages=%s",
            run_id,
            project_id,
            stage,
            repo_dir,
            languages,
        )

        # Step 2: AST Parsing
        stage = "PARSING"
        update_project_status(project_id, "PARSING")
        logger.info(
            "indexing_stage_started run_id=%s project_id=%s stage=%s",
            run_id,
            project_id,
            stage,
        )
        all_chunks = []
        parsed_files_count = 0

        for root, dirs, files in os.walk(repo_dir):
            dirs[:] = [d for d in dirs if d not in [".git", "node_modules", ".venv", "__pycache__", "dist", "build", "target"]]
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in [".py", ".js", ".jsx", ".ts", ".tsx", ".java"]:
                    file_path = os.path.join(root, f)
                    if not allowed_source(Path(repo_dir), Path(file_path)):
                        continue
                    chunks = parse_file(file_path, repo_dir)
                    if chunks:
                        all_chunks.extend(chunks)
                        parsed_files_count += 1

        logger.info(
            "indexing_stage_completed run_id=%s project_id=%s stage=%s "
            "parsed_files=%d chunks=%d",
            run_id,
            project_id,
            stage,
            parsed_files_count,
            len(all_chunks),
        )

        # Step 3: Embeddings & PostgreSQL Store
        stage = "EMBEDDING_PREFLIGHT"
        update_project_status(project_id, "EMBEDDING")
        logger.info(
            "indexing_stage_started run_id=%s project_id=%s stage=%s",
            run_id,
            project_id,
            stage,
        )
        embedding_environment = CodeEmbedder.validate_environment()
        logger.info(
            "indexing_stage_completed run_id=%s project_id=%s stage=%s details=%s",
            run_id,
            project_id,
            stage,
            embedding_environment,
        )

        stage = "EMBEDDING"
        logger.info(
            "indexing_stage_started run_id=%s project_id=%s stage=%s chunks=%d",
            run_id,
            project_id,
            stage,
            len(all_chunks),
        )
        chunk_count = save_code_chunks_to_db(project_id, all_chunks)
        logger.info(
            "indexing_stage_completed run_id=%s project_id=%s stage=%s "
            "stored_chunks=%d",
            run_id,
            project_id,
            stage,
            chunk_count,
        )

        # Step 4: Neo4j Dependency Graph Construction
        stage = "GRAPHING"
        update_project_status(project_id, "GRAPHING")
        logger.info(
            "indexing_stage_started run_id=%s project_id=%s stage=%s",
            run_id,
            project_id,
            stage,
        )
        build_neo4j_graph(project_id, all_chunks)
        logger.info(
            "indexing_stage_completed run_id=%s project_id=%s stage=%s",
            run_id,
            project_id,
            stage,
        )

        # Step 5: Git History Ingestion
        stage = "GIT_INDEXING"
        update_project_status(project_id, "GIT_INDEXING")
        logger.info(
            "indexing_stage_started run_id=%s project_id=%s stage=%s",
            run_id,
            project_id,
            stage,
        )
        commit_count = extract_and_save_git_history(project_id, repo_dir)
        logger.info(
            "indexing_stage_completed run_id=%s project_id=%s stage=%s "
            "stored_commits=%d",
            run_id,
            project_id,
            stage,
            commit_count,
        )

        # Recheck the embedding fingerprint before publishing this generation.
        if fingerprint != embedding_fingerprint():
            raise RuntimeError("Embedding configuration changed during indexing; retry indexing.")
        has_git = (Path(repo_dir) / ".git").exists()
        revision = git.Repo(repo_dir).head.commit.hexsha if has_git else hashlib.sha256(
            "".join(c.file_path + c.code_content for c in all_chunks).encode()
        ).hexdigest()
        save_index(lock_conn, project_id, run_id, fingerprint, revision, has_git, repo_dir)
        # Step 6: Complete
        stage = "FINALIZING"
        update_project_status(
            project_id,
            "READY",
            file_count=parsed_files_count,
            chunk_count=chunk_count,
            commit_count=commit_count,
            languages=languages
        )
        logger.info(
            "indexing_pipeline_completed run_id=%s project_id=%s "
            "files=%d chunks=%d commits=%d elapsed_seconds=%.3f",
            run_id,
            project_id,
            parsed_files_count,
            chunk_count,
            commit_count,
            time.perf_counter() - started_at,
        )

    except Exception as e:
        error_id = str(uuid.uuid4())
        reason = str(e) or repr(e)
        error_msg = (
            f"[{error_id}] Indexing failed at {stage}: "
            f"{type(e).__name__}: {reason}"
        )
        logger.exception(
            "indexing_pipeline_failed run_id=%s error_id=%s project_id=%s "
            "stage=%s exception_type=%s reason=%s elapsed_seconds=%.3f",
            run_id,
            error_id,
            project_id,
            stage,
            type(e).__name__,
            reason,
            time.perf_counter() - started_at,
        )
        update_project_status(project_id, "FAILED", error_msg=error_msg)
