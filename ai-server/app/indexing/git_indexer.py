import os
import git
from datetime import datetime
from typing import List, Dict, Any
from app.database import get_db_connection

def extract_and_save_git_history(project_id: str, repo_dir: str, max_commits: int = 100) -> int:
    git_dir = os.path.join(repo_dir, ".git")
    if not os.path.exists(git_dir):
        print(f"No .git directory found in {repo_dir}. Git evidence will be unavailable.")
        return 0

    try:
        repo = git.Repo(repo_dir)
        commits = list(repo.iter_commits(max_count=max_commits))
    except Exception as e:
        print(f"Error reading Git repository at {repo_dir}: {e}")
        return 0

    conn = get_db_connection()
    cursor = conn.cursor()

    saved_commit_count = 0

    try:
        cursor.execute('DELETE FROM "Commit" WHERE "projectId"=%s', (project_id,))
        for commit in commits:
            committed_at = datetime.fromtimestamp(commit.committed_date)
            commit_hash = commit.hexsha
            author_name = commit.author.name or "Unknown"
            author_email = commit.author.email or "unknown@example.com"
            message = commit.message.strip()

            cursor.execute(
                """
                INSERT INTO "Commit" (
                    "id", "projectId", "commitHash", "authorName", "authorEmail", "message", "committedAt"
                ) VALUES (
                    gen_random_uuid()::text, %s, %s, %s, %s, %s, %s
                ) ON CONFLICT ("projectId", "commitHash") DO NOTHING
                RETURNING "id";
                """,
                (project_id, commit_hash, author_name, author_email, message, committed_at)
            )
            row = cursor.fetchone()
            if not row:
                continue

            commit_id = row[0]
            saved_commit_count += 1

            # Extract changed files diffs
            if commit.parents:
                parent = commit.parents[0]
                diffs = parent.diff(commit, create_patch=True)
            else:
                diffs = commit.diff(git.NULL_TREE, create_patch=True)

            for diff in diffs:
                file_path = diff.b_path or diff.a_path
                if not file_path:
                    continue

                change_type = "modified"
                if diff.new_file:
                    change_type = "added"
                elif diff.deleted_file:
                    change_type = "deleted"

                patch_str = ""
                if diff.diff:
                    patch_str = diff.diff.decode("utf-8", errors="ignore")[:3000] # max 3k chars diff

                cursor.execute(
                    """
                    INSERT INTO "CommitChange" (
                        "id", "commitId", "filePath", "changeType", "additions", "deletions", "diff"
                    ) VALUES (
                        gen_random_uuid()::text, %s, %s, %s, %s, %s, %s
                    );
                    """,
                    (commit_id, file_path, change_type, 0, 0, patch_str)
                )

        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error saving Git history to DB: {e}")
        raise e
    finally:
        cursor.close()
        conn.close()

    print(f"Indexed {saved_commit_count} commits for project {project_id}")
    return saved_commit_count

def create_synthetic_git_history(project_id: str, repo_dir: str) -> int:
    """Fallback for ZIP uploads without Git history"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO "Commit" (
                "id", "projectId", "commitHash", "authorName", "authorEmail", "message", "committedAt"
            ) VALUES (
                gen_random_uuid()::text, %s, 'initial-snapshot-0000000000000000', 'CodeLens AI', 'system@codelens.ai', 'Initial Repository Ingestion Snapshot', NOW()
            ) ON CONFLICT ("projectId", "commitHash") DO NOTHING;
            """,
            (project_id,)
        )
        conn.commit()
    finally:
        cursor.close()
        conn.close()

    return 1
