"""python -m app.cli setup | doctor [--probe-model]."""
import argparse
import json
from pathlib import Path

from app.config import settings
from app.database import get_db_connection
from app.embeddings.fingerprint import embedding_fingerprint
from app.indexing.embedder import CodeEmbedder
from app.llm.factory import reasoning_profile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["setup", "doctor"])
    parser.add_argument("--probe-model", action="store_true")
    args = parser.parse_args()
    if args.command == "setup":
        sql = Path(__file__).resolve().parents[2] / "server" / "prisma" / "agentic-mvp.sql"
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(sql.read_text())
            conn.commit()
        finally:
            conn.close()
        print("MVP schema ready. Reindex legacy projects before analysis.")
        return
    report = {"reasoning": reasoning_profile(), "embeddings": embedding_fingerprint()}
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('\"RepositoryIndex\"')")
            report["schema_ready"] = cur.fetchone()[0] is not None
    finally:
        conn.close()
    if args.probe_model:
        from app.agents.budgets import Budget
        from app.agents.contracts import BugSignals
        from app.llm.structured_output import ModelGateway
        report["embedding_probe"] = CodeEmbedder.validate_environment()
        result = ModelGateway(Budget()).generate("understand", {"bug": "Login fails with session expired."}, BugSignals)
        report["reasoning_probe"] = result.model_dump()
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
