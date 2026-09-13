import logging
from typing import List

from app.config import settings
from app.database import get_db_connection
from app.indexing.parser import CodeChunkData
from app.embeddings.gemini import GeminiEmbedder, EmbeddingError, QUERY_TASK_TYPE, RETRIEVAL_TASK_TYPE
from app.embeddings.local import embed_local

logger = logging.getLogger(__name__)


class CodeEmbedder:
    @classmethod
    def embed_text(cls, text: str) -> list[float]:
        return cls.embed_batch([text], task_type=QUERY_TASK_TYPE)[0]

    @classmethod
    def embed_batch(cls, texts, batch_size=None, task_type=RETRIEVAL_TASK_TYPE):
        if settings.EMBEDDING_PROVIDER == "local":
            return embed_local(texts, query=task_type == QUERY_TASK_TYPE)
        return GeminiEmbedder.embed_batch(texts, batch_size=batch_size, task_type=task_type)

    @classmethod
    def validate_environment(cls):
        vectors = cls.embed_batch(["def healthcheck(): return True"])
        return {
            "ready": True, "provider": settings.EMBEDDING_PROVIDER,
            "model": settings.LOCAL_EMBEDDING_MODEL if settings.EMBEDDING_PROVIDER == "local" else settings.EMBEDDING_MODEL_NAME,
            "dimension": len(vectors[0]), "expected_dimension": settings.EMBEDDING_DIMENSION,
        }


def save_code_chunks_to_db(project_id: str, chunks: List[CodeChunkData]) -> int:
    if not chunks:
        logger.info("embedding_skipped project_id=%s reason=no_chunks", project_id)
        return 0

    # Format texts for embedding
    texts_to_embed = []
    for c in chunks:
        text = (
            f"File: {c.file_path}\n"
            f"Class: {c.class_name or 'N/A'}\n"
            f"Function: {c.function_name}\n"
            f"Signature: {c.signature or ''}\n"
            f"Code:\n{c.code_content}"
        )
        if len(text) > settings.EMBEDDING_MAX_CHARS:
            logger.warning(
                "embedding_input_truncated project_id=%s file=%s function=%s "
                "original_chars=%d retained_chars=%d",
                project_id,
                c.file_path,
                c.function_name,
                len(text),
                settings.EMBEDDING_MAX_CHARS,
            )
            text = text[:settings.EMBEDDING_MAX_CHARS]
        texts_to_embed.append(text)

    logger.info(
        "embedding_generation_started project_id=%s chunks=%d batch_size=%d",
        project_id,
        len(chunks),
        settings.EMBEDDING_BATCH_SIZE,
    )
    embeddings = CodeEmbedder.embed_batch(texts_to_embed)

    conn = get_db_connection()
    cursor = conn.cursor()

    inserted_count = 0
    try:
        # Make re-indexing idempotent while retaining old chunks if this transaction fails.
        cursor.execute(
            'DELETE FROM "CodeChunk" WHERE "projectId" = %s;',
            (project_id,),
        )
        for chunk, emb in zip(chunks, embeddings):
            # Format vector for pgvector literal e.g. '[0.1, 0.2, ...]'
            vec_str = f"[{','.join(map(str, emb))}]"

            cursor.execute(
                """
                INSERT INTO "CodeChunk" (
                    "id", "projectId", "filePath", "language", "chunkType",
                    "className", "functionName", "signature", "codeContent",
                    "startLine", "endLine", "imports", "calls", "embedding"
                ) VALUES (
                    gen_random_uuid()::text, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s, %s::vector
                ) RETURNING "id";
                """,
                (
                    project_id,
                    chunk.file_path,
                    chunk.language,
                    chunk.chunk_type,
                    chunk.class_name,
                    chunk.function_name,
                    chunk.signature,
                    chunk.code_content,
                    chunk.start_line,
                    chunk.end_line,
                    chunk.imports,
                    chunk.calls,
                    vec_str,
                )
            )
            inserted_count += 1

        conn.commit()
        logger.info(
            "embedding_database_write_completed project_id=%s inserted_chunks=%d",
            project_id,
            inserted_count,
        )
    except Exception as e:
        conn.rollback()
        logger.exception(
            "embedding_database_write_failed project_id=%s inserted_before_failure=%d "
            "exception_type=%s reason=%s",
            project_id,
            inserted_count,
            type(e).__name__,
            str(e) or repr(e),
        )
        raise EmbeddingError(
            f"Failed to store embeddings for project {project_id} after "
            f"{inserted_count}/{len(chunks)} inserts "
            f"({type(e).__name__}: {str(e) or repr(e)})"
        ) from e
    finally:
        cursor.close()
        conn.close()

    return inserted_count
