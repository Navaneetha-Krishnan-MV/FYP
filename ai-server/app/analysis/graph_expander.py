from typing import List, Dict, Any, Tuple
from app.database import Neo4jManager, get_db_connection

def expand_graph_neighbors(
    project_id: str,
    seed_candidates: List[Dict[str, Any]],
    hops: int = 2,
    lambda_decay: float = 0.5
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Step 2 of AGTR: Adaptive Graph Propagation G(v)
    Traverses Neo4j for 1..hops and calculates G(v) with distance decay.
    """
    if not seed_candidates:
        return [], []

    seed_chunk_ids = [c["chunk_id"] for c in seed_candidates if c.get("chunk_id")]
    seed_scores = {c["chunk_id"]: float(c.get("semantic_score", 0.0)) for c in seed_candidates if c.get("chunk_id")}

    graph_scores = {c["chunk_id"]: float(c.get("semantic_score", 0.0)) for c in seed_candidates if c.get("chunk_id")}
    dependency_paths = []

    try:
        # Query Neo4j for 1..hops paths starting from seed chunkIds
        cypher = f"""
        MATCH (seed:Function {{projectId: $projectId}})
        WHERE seed.chunkId IN $seedChunkIds
        MATCH path = (seed)-[:CALLS|DEPENDS_ON*1..{hops}]-(target:Function {{projectId: $projectId}})
        RETURN
            seed.chunkId AS seedChunkId,
            target.chunkId AS targetChunkId,
            target.name AS targetName,
            target.filePath AS targetPath,
            length(path) AS distance,
            [n IN nodes(path) | coalesce(n.name, n.path)] AS pathNodes
        LIMIT 100;
        """

        records = Neo4jManager.execute_cypher(cypher, {
            "projectId": project_id,
            "seedChunkIds": seed_chunk_ids
        })

        new_chunk_ids_to_fetch = set()

        for r in records:
            s_id = r.get("seedChunkId")
            t_id = r.get("targetChunkId")
            dist = r.get("distance", 1)
            nodes = r.get("pathNodes", [])

            if nodes:
                path_str = " -> ".join(nodes)
                if path_str not in dependency_paths:
                    dependency_paths.append(path_str)

            if not t_id:
                continue

            s_score = seed_scores.get(s_id, 0.5)
            propagated_score = s_score * (lambda_decay ** dist)

            # Accumulate graph score G(v)
            if t_id in graph_scores:
                graph_scores[t_id] = max(graph_scores[t_id], propagated_score)
            else:
                graph_scores[t_id] = propagated_score
                new_chunk_ids_to_fetch.add(t_id)

    except Exception as e:
        print(f"Neo4j graph expansion warning: {e}")

    # Build merged candidate list including seeds and graph-discovered neighbors
    candidate_map = {c["chunk_id"]: dict(c) for c in seed_candidates if c.get("chunk_id")}

    # Fetch details for newly discovered neighbor chunks from Postgres
    if new_chunk_ids_to_fetch:
        fetched_neighbors = fetch_chunks_by_ids(list(new_chunk_ids_to_fetch))
        for fn in fetched_neighbors:
            candidate_map[fn["chunk_id"]] = fn

    # Update graph_score G(v) for all candidates in candidate_map
    all_candidates = []
    for chunk_id, c in candidate_map.items():
        g_val = graph_scores.get(chunk_id, 0.0)
        c["graph_score"] = round(g_val, 4)
        if "semantic_score" not in c:
            c["semantic_score"] = 0.0
        all_candidates.append(c)

    return all_candidates, dependency_paths[:10]

def fetch_chunks_by_ids(chunk_ids: List[str]) -> List[Dict[str, Any]]:
    if not chunk_ids:
        return []

    conn = get_db_connection()
    cursor = conn.cursor()
    neighbors = []

    try:
        cursor.execute(
            """
            SELECT
                "id", "filePath", "functionName", "className", "chunkType",
                "signature", "codeContent", "startLine", "endLine", "imports", "calls"
            FROM "CodeChunk"
            WHERE "id" = ANY(%s);
            """,
            (chunk_ids,)
        )
        rows = cursor.fetchall()
        for r in rows:
            neighbors.append({
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
                "semantic_score": 0.0,
                "graph_score": 0.0,
            })
    except Exception as e:
        print(f"Error fetching chunk neighbors from DB: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

    return neighbors
