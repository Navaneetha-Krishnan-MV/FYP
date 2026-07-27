from typing import List
from app.database import Neo4jManager
from app.indexing.parser import CodeChunkData
from app.database import get_db_connection

def build_neo4j_graph(project_id: str, chunks: List[CodeChunkData]) -> int:
    # First, fetch chunk IDs from DB to map chunks to chunkId
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT "id", "filePath", "functionName", "startLine" FROM "CodeChunk" WHERE "projectId" = %s;',
        (project_id,)
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    chunk_id_map = {}
    for r in rows:
        key = (r[1], r[2], r[3]) # (filePath, functionName, startLine)
        chunk_id_map[key] = r[0]

    # Clean existing graph nodes for this project
    Neo4jManager.execute_cypher(
        "MATCH (n {projectId: $projectId}) DETACH DELETE n;",
        {"projectId": project_id}
    )

    created_nodes_count = 0

    # 1. Create File and Class nodes
    files_created = set()
    classes_created = set()

    for c in chunks:
        # Create File node
        if c.file_path not in files_created:
            Neo4jManager.execute_cypher(
                """
                MERGE (f:File {path: $path, projectId: $projectId})
                SET f.language = $language
                """,
                {"path": c.file_path, "projectId": project_id, "language": c.language}
            )
            files_created.add(c.file_path)

        # Create Class node if present
        if c.class_name:
            class_key = f"{c.file_path}::{c.class_name}"
            if class_key not in classes_created:
                Neo4jManager.execute_cypher(
                    """
                    MERGE (c:Class {name: $className, filePath: $path, projectId: $projectId})
                    WITH c
                    MATCH (f:File {path: $path, projectId: $projectId})
                    MERGE (f)-[:CONTAINS]->(c)
                    """,
                    {"className": c.class_name, "path": c.file_path, "projectId": project_id}
                )
                classes_created.add(class_key)

        # Create Function node
        chunk_id = chunk_id_map.get((c.file_path, c.function_name, c.start_line), "")
        Neo4jManager.execute_cypher(
            """
            CREATE (fn:Function {
                name: $functionName,
                filePath: $path,
                className: $className,
                startLine: $startLine,
                endLine: $endLine,
                chunkId: $chunkId,
                projectId: $projectId
            })
            WITH fn
            MATCH (f:File {path: $path, projectId: $projectId})
            CREATE (f)-[:CONTAINS]->(fn)
            """,
            {
                "functionName": c.function_name,
                "path": c.file_path,
                "className": c.class_name or "",
                "startLine": c.start_line,
                "endLine": c.end_line,
                "chunkId": chunk_id,
                "projectId": project_id,
            }
        )
        created_nodes_count += 1

        # Link Class -> Function if class present
        if c.class_name:
            Neo4jManager.execute_cypher(
                """
                MATCH (c:Class {name: $className, filePath: $path, projectId: $projectId})
                MATCH (fn:Function {chunkId: $chunkId, projectId: $projectId})
                MERGE (c)-[:CONTAINS]->(fn)
                """,
                {
                    "className": c.class_name,
                    "path": c.file_path,
                    "chunkId": chunk_id,
                    "projectId": project_id,
                }
            )

    # 2. Create CALLS and DEPENDS_ON relationships
    for c in chunks:
        caller_chunk_id = chunk_id_map.get((c.file_path, c.function_name, c.start_line), "")
        if not caller_chunk_id or not c.calls:
            continue

        for callee_name in c.calls:
            Neo4jManager.execute_cypher(
                """
                MATCH (caller:Function {chunkId: $callerChunkId, projectId: $projectId})
                MATCH (callee:Function {name: $calleeName, projectId: $projectId})
                WHERE caller <> callee
                MERGE (caller)-[:CALLS]->(callee)
                MERGE (caller)-[:DEPENDS_ON]->(callee)
                """,
                {
                    "callerChunkId": caller_chunk_id,
                    "calleeName": callee_name,
                    "projectId": project_id,
                }
            )

    print(f"Built Neo4j graph for project {project_id}: {created_nodes_count} function nodes created.")
    return created_nodes_count
