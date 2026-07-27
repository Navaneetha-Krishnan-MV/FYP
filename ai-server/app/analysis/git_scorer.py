import math
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple
from app.database import get_db_connection

def compute_git_temporal_scores(
    project_id: str,
    candidates: List[Dict[str, Any]],
    bug_search_terms: List[str],
    mu_decay: float = 0.05
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Step 3 of AGTR: Temporal Git Decay T(v) = R(v) * e^(-mu * delta_t)
    """
    if not candidates:
        return candidates, []

    conn = get_db_connection()
    cursor = conn.cursor()

    git_evidence_commits = []

    try:
        # Fetch all commits for this project with changes
        cursor.execute(
            """
            SELECT
                c."commitHash",
                c."authorName",
                c."message",
                c."committedAt",
                cc."filePath",
                cc."diff"
            FROM "Commit" c
            JOIN "CommitChange" cc ON c."id" = cc."commitId"
            WHERE c."projectId" = %s
            ORDER BY c."committedAt" DESC
            LIMIT 100;
            """,
            (project_id,)
        )
        rows = cursor.fetchall()

        now = datetime.now(timezone.utc)
        file_git_stats = {}

        for r in rows:
            commit_hash = r[0]
            author = r[1]
            message = r[2]
            committed_at = r[3]
            file_path = r[4]
            diff = r[5] or ""

            # Ensure timezone awareness for subtraction
            if committed_at.tzinfo is None:
                committed_at = committed_at.replace(tzinfo=timezone.utc)

            delta_days = max(0.0, (now - committed_at).total_seconds() / 86400.0)

            # Compute message & diff relevance R(v)
            r_v = 0.3 # base score for any modified file
            message_lower = message.lower()
            diff_lower = diff.lower()

            for term in bug_search_terms:
                term_lower = term.lower()
                if term_lower in message_lower:
                    r_v += 0.4
                if term_lower in diff_lower:
                    r_v += 0.3

            r_v = min(1.0, r_v)

            # Exponential decay: e^(-mu * delta_t)
            time_decay = math.exp(-mu_decay * delta_days)
            t_score = r_v * time_decay

            if file_path not in file_git_stats or t_score > file_git_stats[file_path]["git_score"]:
                file_git_stats[file_path] = {
                    "git_score": round(t_score, 4),
                    "latest_commit": commit_hash[:8],
                    "message": message,
                    "author": author,
                    "date": committed_at.strftime("%Y-%m-%d"),
                    "diff": diff
                }

            if r_v > 0.4 and len(git_evidence_commits) < 5:
                git_evidence_commits.append({
                    "hash": commit_hash[:8],
                    "author": author,
                    "date": committed_at.strftime("%Y-%m-%d"),
                    "message": message,
                    "diff": diff[:500]
                })

        # Assign git_score to each candidate based on file_path match
        for c in candidates:
            fp = c.get("file_path", "")
            stats = file_git_stats.get(fp)
            if stats:
                c["git_score"] = stats["git_score"]
                c["latest_commit"] = stats["latest_commit"]
            else:
                c["git_score"] = 0.1 # baseline low git score
                c["latest_commit"] = "N/A"

    except Exception as e:
        print(f"Git temporal scoring warning: {e}")
        for c in candidates:
            c["git_score"] = 0.1
            c["latest_commit"] = "N/A"
    finally:
        cursor.close()
        conn.close()

    return candidates, git_evidence_commits
