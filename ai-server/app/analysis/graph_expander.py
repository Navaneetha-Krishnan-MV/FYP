from typing import List, Dict, Any, Tuple
import networkx as nx
from app.database import Neo4jManager, get_db_connection


def fetch_call_graph_edges(project_id: str) -> List[Tuple[str, str]]:
    """
    Fetch every CALLS/DEPENDS_ON edge between Function nodes in this
    project from Neo4j, as (chunkId_a, chunkId_b) pairs. No hop limit:
    PageRank needs the full graph structure to be correct, not a
    hop-limited neighborhood.
    """
    cypher = """
    MATCH (a:Function {projectId: $projectId})-[:CALLS|DEPENDS_ON]-(b:Function {projectId: $projectId})
    RETURN DISTINCT a.chunkId AS a, b.chunkId AS b;
    """
    records = Neo4jManager.execute_cypher(cypher, {"projectId": project_id})
    return [(r["a"], r["b"]) for r in records if r.get("a") and r.get("b")]


def compute_personalized_pagerank(
    edges: List[Tuple[str, str]],
    personalization: Dict[str, float],
    alpha: float = 0.85,
) -> Dict[str, float]:
    """
    Personalized PageRank over an undirected graph of the given edges,
    restarting toward `personalization` (the semantic seed set, weighted
    by semantic score). Undirected to match the existing Neo4j hop
    traversal's undirected semantics: a function's structural
    neighborhood includes both what it calls and what calls it.

    Returns {} if there's no graph structure or no restart mass to
    personalize toward - callers should fall back to another signal
    (e.g. each node's own semantic score) in that case.
    """
    if not edges or not personalization:
        return {}

    total = sum(personalization.values())
    if total <= 0:
        return {}
    normalized_personalization = {k: v / total for k, v in personalization.items()}

    graph = nx.Graph()
    graph.add_edges_from(edges)
    # Ensure every personalized (seed) node exists in the graph even if it
    # has no edges, so it can still receive its own restart mass.
    graph.add_nodes_from(normalized_personalization.keys())

    return nx.pagerank(graph, alpha=alpha, personalization=normalized_personalization)


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

    dependency_paths = []
    new_chunk_ids_to_fetch = set()
    discovered_chunk_ids = set(seed_chunk_ids)

    try:
        # Query Neo4j for 1..hops paths starting from seed chunkIds, purely
        # to determine which nodes are in scope and to build dependency
        # path strings. Structural scoring itself comes from PageRank below.
        cypher = f"""
        MATCH (seed:Function {{projectId: $projectId}})
        WHERE seed.chunkId IN $seedChunkIds
        MATCH path = (seed)-[:CALLS|DEPENDS_ON*1..{hops}]-(target:Function {{projectId: $projectId}})
        RETURN
            target.chunkId AS targetChunkId,
            [n IN nodes(path) | coalesce(n.name, n.path)] AS pathNodes
        LIMIT 100;
        """

        records = Neo4jManager.execute_cypher(cypher, {
            "projectId": project_id,
            "seedChunkIds": seed_chunk_ids
        })

        for r in records:
            t_id = r.get("targetChunkId")
            nodes = r.get("pathNodes", [])

            if nodes:
                path_str = " -> ".join(nodes)
                if path_str not in dependency_paths:
                    dependency_paths.append(path_str)

            if t_id and t_id not in discovered_chunk_ids:
                discovered_chunk_ids.add(t_id)
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

    # Score structural relevance via Personalized PageRank over the whole
    # project call graph, falling back to each node's own semantic score
    # (safe, degenerate-but-non-crashing behavior) if PageRank can't run.
    pagerank_scores: Dict[str, float] = {}
    try:
        edges = fetch_call_graph_edges(project_id)
        pagerank_scores = compute_personalized_pagerank(edges, seed_scores)
    except Exception as e:
        print(f"Personalized PageRank warning: {e}")

    all_candidates = []
    for chunk_id, c in candidate_map.items():
        if chunk_id in pagerank_scores:
            g_val = pagerank_scores[chunk_id]
        else:
            g_val = seed_scores.get(chunk_id, c.get("semantic_score", 0.0))
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
