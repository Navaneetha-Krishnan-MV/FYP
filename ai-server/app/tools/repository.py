"""Tools receive a trusted project scope; no model-supplied SQL or paths."""
from psycopg2.extras import RealDictCursor

from app.database import Neo4jManager
from app.indexing.embedder import CodeEmbedder

CHUNK_COLUMNS = '''"id" AS chunk_id, "filePath" AS file_path,
    "functionName" AS function_name, "startLine" AS start_line,
    "endLine" AS end_line, "codeContent" AS code_content'''


class RepositoryTools:
    def __init__(self, conn, project_id: str, index: dict):
        self.conn, self.project_id, self.index = conn, project_id, index

    def rows(self, query, args):
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, args)
            return [dict(r) for r in cur.fetchall()]

    def chunk(self, chunk_id):
        rows = self.rows(f'SELECT {CHUNK_COLUMNS} FROM "CodeChunk" WHERE "projectId"=%s AND "id"=%s', (self.project_id, chunk_id))
        if not rows:
            raise ValueError("Unknown chunk in this project")
        return rows[0]

    def keyword_search(self, query, limit=5):
        # POSITION is literal matching: '%' and '_' have no special meaning.
        return self.rows(f'''SELECT {CHUNK_COLUMNS} FROM "CodeChunk"
            WHERE "projectId"=%s AND (position(lower(%s) in lower("codeContent")) > 0
            OR position(lower(%s) in lower("functionName")) > 0)
            ORDER BY "filePath", "startLine" LIMIT %s''', (self.project_id, query, query, limit))

    def semantic_search(self, query, limit=5):
        vector = str(CodeEmbedder.embed_text(query))
        return self.rows(f'''SELECT {CHUNK_COLUMNS}, 1-("embedding" <=> %s::vector) AS semantic_score
            FROM "CodeChunk" WHERE "projectId"=%s AND "embedding" IS NOT NULL
            ORDER BY "embedding" <=> %s::vector LIMIT %s''', (vector, self.project_id, vector, limit))

    def read_code(self, chunk_id, offset=0, lines=80):
        chunk = self.chunk(chunk_id)
        source_lines = chunk["code_content"].splitlines()
        if offset >= len(source_lines):
            raise ValueError("Read offset is outside this chunk")
        selected = source_lines[offset:offset + lines]
        # Bound without cutting a line while reporting a complete line citation.
        while len("\n".join(selected)) > 6000 and len(selected) > 1:
            selected.pop()
        if len("\n".join(selected)) > 6000:
            raise ValueError("Source line exceeds tool output limit")
        chunk["code_content"] = "\n".join(selected)
        chunk["start_line"] += offset
        chunk["end_line"] = chunk["start_line"] + len(selected) - 1
        chunk["truncated"] = offset > 0 or offset + len(selected) < len(source_lines)
        return chunk

    def git_history(self, chunk_id, limit=3):
        chunk = self.chunk(chunk_id)
        if not self.index["has_git"]:
            raise LookupError("This index has no Git history")
        return self.rows('''SELECT c."commitHash" AS commit_hash, c."message",
            cc."filePath" AS file_path, cc."diff", c."committedAt" AS committed_at
            FROM "Commit" c JOIN "CommitChange" cc ON cc."commitId"=c.id
            WHERE c."projectId"=%s AND cc."filePath"=%s
            AND c."commitHash" <> 'initial-snapshot-0000000000000000'
            ORDER BY c."committedAt" DESC LIMIT %s''', (self.project_id, chunk["file_path"], limit))

    def dependency_neighbors(self, chunk_id):
        self.chunk(chunk_id)
        records = Neo4jManager.execute_cypher('''
            MATCH (a:Function {projectId: $project, chunkId: $chunk})-[r:CALLS]-(b:Function {projectId: $project})
            RETURN DISTINCT b.chunkId AS chunk_id, startNode(r).chunkId AS caller_id,
            endNode(r).chunkId AS callee_id LIMIT 15''', {"project": self.project_id, "chunk": chunk_id})
        return [{**r, "resolution": "approximate_name_match"} for r in records]
