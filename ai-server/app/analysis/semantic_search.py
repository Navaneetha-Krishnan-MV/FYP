from typing import List, Dict, Any
from app.database import get_db_connection
from app.indexing.embedder import CodeEmbedder

def search_semantic_candidates(project_id: str, query_text: str, top_k: int = 15) -> List[Dict[str, Any]]:
    embedder = CodeEmbedder()
    query_vector = embedder.embed_text(query_text)
    vec_str = f"[{','.join(map(str, query_vector))}]"

    conn = get_db_connection()
    cursor = conn.cursor()

    candidates = []

    try:
        # Use cosine distance (<=>) in pgvector: similarity = 1 - distance
        cursor.execute(
            """
            SELECT
                "id",
                "filePath",
                "functionName",
                "className",
                "chunkType",
                "signature",
                "codeContent",
                "startLine",
                "endLine",
                "imports",
                "calls",
                (1 - ("embedding" <=> %s::vector)) AS similarity
            FROM "CodeChunk"
            WHERE "projectId" = %s AND "embedding" IS NOT NULL
            ORDER BY similarity DESC
            LIMIT %s;
            """,
            (vec_str, project_id, top_k)
        )

        rows = cursor.fetchall()
        for r in rows:
            sim = float(r[11]) if r[11] is not None else 0.0
            # Ensure similarity is normalized between 0.0 and 1.0
            sim_score = max(0.0, min(1.0, sim))

            candidates.append({
                "chunk_id": r[0],
                "file_path": r[1],
                "function_name": r[2],
                "class_name": r[3],
                "chunk_type": r[4],
                "signature": r[5],
                "code_content": r[6],
                "start_line": r[7],
                "end_line": r[8],
                "imports": r[9] or [],
                "calls": r[10] or [],
                "semantic_score": sim_score,
            })
    except Exception as e:
        print(f"Error in semantic pgvector search: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

    return candidates
