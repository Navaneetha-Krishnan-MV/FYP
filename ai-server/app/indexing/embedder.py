import logging
import random
import threading
import time
from typing import Any, Dict, List

from google.genai import types

from app.config import settings
from app.database import get_db_connection
from app.indexing.parser import CodeChunkData
from app.llm.gemini_client import GeminiClient

logger = logging.getLogger(__name__)

RETRIEVAL_TASK_TYPE = "RETRIEVAL_DOCUMENT"
QUERY_TASK_TYPE = "CODE_RETRIEVAL_QUERY"
RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}


class EmbeddingError(RuntimeError):
    """An embedding setup, inference, validation, or persistence failure."""


class _EmbeddingRequestPacer:
    """Space embedding requests across all indexing jobs in this process."""

    _lock = threading.Lock()
    _next_request_at = 0.0

    @classmethod
    def wait(cls) -> None:
        requests_per_minute = settings.EMBEDDING_REQUESTS_PER_MINUTE
        if requests_per_minute < 1:
            raise EmbeddingError(
                "EMBEDDING_REQUESTS_PER_MINUTE must be at least 1, got "
                f"{requests_per_minute}"
            )

        interval_seconds = 60.0 / requests_per_minute
        with cls._lock:
            delay = max(0.0, cls._next_request_at - time.monotonic())
            if delay:
                logger.info(
                    "embedding_request_paced delay_seconds=%.3f "
                    "requests_per_minute=%d",
                    delay,
                    requests_per_minute,
                )
                time.sleep(delay)
            cls._next_request_at = time.monotonic() + interval_seconds


def _is_retryable_error(exc: Exception) -> bool:
    status_code = getattr(exc, "code", None)
    if status_code is None:
        status_code = getattr(exc, "status_code", None)
    if status_code in RETRYABLE_STATUS_CODES:
        return True

    # The SDK may surface transport failures without an HTTP status.
    return isinstance(exc, (ConnectionError, TimeoutError))


def _retry_delay_seconds(failed_attempt: int) -> float:
    base = settings.EMBEDDING_RETRY_BASE_SECONDS
    maximum = settings.EMBEDDING_RETRY_MAX_SECONDS
    if base <= 0 or maximum <= 0:
        raise EmbeddingError(
            "Embedding retry delays must be greater than zero"
        )
    exponential_delay = min(maximum, base * (2 ** (failed_attempt - 1)))
    return min(maximum, exponential_delay + random.uniform(0, base))


class CodeEmbedder:
    @classmethod
    def embed_text(cls, text: str) -> List[float]:
        return cls.embed_batch([text], task_type=QUERY_TASK_TYPE)[0]

    @classmethod
    def embed_batch(
        cls,
        texts: List[str],
        batch_size: int | None = None,
        task_type: str = RETRIEVAL_TASK_TYPE,
    ) -> List[List[float]]:
        if not texts:
            return []

        client = GeminiClient.get_client()
        if client is None:
            raise EmbeddingError(
                "GEMINI_API_KEY is not set; the Gemini embedding API requires it. "
                "Set GEMINI_API_KEY in ai-server/.env."
            )

        effective_batch_size = batch_size or settings.EMBEDDING_BATCH_SIZE
        if effective_batch_size < 1:
            raise EmbeddingError(
                f"EMBEDDING_BATCH_SIZE must be at least 1, got {effective_batch_size}"
            )
        if settings.EMBEDDING_MAX_ATTEMPTS < 1:
            raise EmbeddingError(
                "EMBEDDING_MAX_ATTEMPTS must be at least 1, got "
                f"{settings.EMBEDDING_MAX_ATTEMPTS}"
            )

        all_vectors: List[List[float]] = []
        total_batches = (len(texts) + effective_batch_size - 1) // effective_batch_size
        started_at = time.perf_counter()

        for batch_number, start in enumerate(
            range(0, len(texts), effective_batch_size),
            start=1,
        ):
            batch = texts[start:start + effective_batch_size]
            logger.info(
                "embedding_batch_started batch=%d/%d items=%d task_type=%s "
                "max_input_chars=%d",
                batch_number,
                total_batches,
                len(batch),
                task_type,
                len(max(batch, key=len)),
            )

            last_exc: Exception | None = None
            for attempt in range(1, settings.EMBEDDING_MAX_ATTEMPTS + 1):
                try:
                    _EmbeddingRequestPacer.wait()
                    response = client.models.embed_content(
                        model=settings.EMBEDDING_MODEL_NAME,
                        contents=batch,
                        config=types.EmbedContentConfig(
                            task_type=task_type,
                            output_dimensionality=settings.EMBEDDING_DIMENSION,
                        ),
                    )
                    if not response.embeddings:
                        raise EmbeddingError(
                            "Gemini returned no embeddings for a non-empty batch"
                        )
                    batch_vectors = [list(e.values) for e in response.embeddings]
                    if len(batch_vectors) != len(batch):
                        raise EmbeddingError(
                            "Embedding response count mismatch: requested "
                            f"{len(batch)}, received {len(batch_vectors)}"
                        )
                    invalid_dimensions = {
                        len(vector)
                        for vector in batch_vectors
                        if len(vector) != settings.EMBEDDING_DIMENSION
                    }
                    if invalid_dimensions:
                        raise EmbeddingError(
                            "Embedding dimension mismatch during inference: expected "
                            f"{settings.EMBEDDING_DIMENSION}, received "
                            f"{sorted(invalid_dimensions)}"
                        )
                    all_vectors.extend(batch_vectors)
                    logger.info(
                        "embedding_batch_completed batch=%d/%d embedded_total=%d/%d",
                        batch_number,
                        total_batches,
                        len(all_vectors),
                        len(texts),
                    )
                    last_exc = None
                    break
                except Exception as exc:
                    last_exc = exc
                    retryable = _is_retryable_error(exc)
                    if (
                        isinstance(exc, EmbeddingError)
                        or not retryable
                        or attempt == settings.EMBEDDING_MAX_ATTEMPTS
                    ):
                        break
                    backoff = _retry_delay_seconds(attempt)
                    logger.warning(
                        "embedding_batch_retry batch=%d/%d attempt=%d/%d "
                        "backoff_seconds=%.3f exception_type=%s status_code=%s "
                        "reason=%s",
                        batch_number,
                        total_batches,
                        attempt,
                        settings.EMBEDDING_MAX_ATTEMPTS,
                        backoff,
                        type(exc).__name__,
                        getattr(exc, "code", getattr(exc, "status_code", None)),
                        str(exc) or repr(exc),
                    )
                    time.sleep(backoff)

            if last_exc is not None:
                logger.exception(
                    "embedding_batch_failed batch=%d/%d items=%d "
                    "exception_type=%s reason=%s",
                    batch_number,
                    total_batches,
                    len(batch),
                    type(last_exc).__name__,
                    str(last_exc) or repr(last_exc),
                    exc_info=last_exc,
                )
                if isinstance(last_exc, EmbeddingError):
                    raise last_exc
                raise EmbeddingError(
                    f"Embedding inference failed in batch {batch_number}/{total_batches} "
                    f"after {attempt} attempt(s) "
                    f"({type(last_exc).__name__}: {str(last_exc) or repr(last_exc)})"
                ) from last_exc

        logger.info(
            "embedding_inference_completed items=%d batches=%d elapsed_seconds=%.3f",
            len(all_vectors),
            total_batches,
            time.perf_counter() - started_at,
        )
        return all_vectors

    @classmethod
    def validate_environment(cls) -> Dict[str, Any]:
        """Run a probe embedding call against the configured Gemini model."""
        logger.info(
            "embedding_preflight_started model=%s dimension=%d",
            settings.EMBEDDING_MODEL_NAME,
            settings.EMBEDDING_DIMENSION,
        )
        started_at = time.perf_counter()
        vectors = cls.embed_batch(
            ["def codelens_embedding_healthcheck():\n    return True"],
            batch_size=1,
        )
        details = {
            "ready": True,
            "model": settings.EMBEDDING_MODEL_NAME,
            "dimension": len(vectors[0]),
            "expected_dimension": settings.EMBEDDING_DIMENSION,
            "provider": "gemini",
            "elapsed_seconds": round(time.perf_counter() - started_at, 3),
        }
        logger.info("embedding_preflight_completed details=%s", details)
        return details

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
