import math
import re
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple
from app.database import get_db_connection

_HUNK_HEADER_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", re.MULTILINE)


def parse_diff_hunks(patch_text: str) -> List[Tuple[int, int]]:
    """
    Extract post-change (new-file) line ranges from unified diff hunk
    headers, e.g. '@@ -10,5 +12,7 @@' covers new-file lines 12..18.
    A patch may contain multiple hunks; all are returned.
    """
    if not patch_text:
        return []

    ranges = []
    for match in _HUNK_HEADER_RE.finditer(patch_text):
        start = int(match.group(1))
        length = int(match.group(2)) if match.group(2) else 1
        end = start + max(length - 1, 0)
        ranges.append((start, end))
    return ranges


def hunks_overlap_range(hunks: List[Tuple[int, int]], start_line: int, end_line: int) -> bool:
    """True if any hunk's line range overlaps [start_line, end_line]."""
    for hunk_start, hunk_end in hunks:
        if hunk_start <= end_line and start_line <= hunk_end:
            return True
    return False


def compute_git_temporal_scores(
    project_id: str,
    candidates: List[Dict[str, Any]],
    bug_search_terms: List[str],
    mu_decay: float = 0.05,
    *, connection=None, as_of=None, strict=False, aligned_revision=None, metadata=None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Step 3 of AGTR: Temporal Git Decay T(v) = R(v) * e^(-mu * delta_t)

    R(v) is scored per function, not per file: a commit's diff hunks are
    checked for line-range overlap against each candidate's own
    [start_line, end_line]. A direct hit (the commit touched this exact
    function) scores higher than a same-file-but-different-function touch.
    """
    if not candidates:
        return candidates, []

    conn = connection or get_db_connection()
    cursor = conn.cursor()

    git_evidence_commits = []

    try:
        # Fetch all commits for this project with changes
        cutoff = as_of or datetime.now(timezone.utc)
        extra_filter = ' AND c."committedAt" <= %s AND cc."filePath" = ANY(%s)' if strict else ''
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
            """ + extra_filter + """
            ORDER BY c."committedAt" DESC, c."commitHash", cc."filePath", cc.id
            LIMIT 100;
            """,
            (project_id, cutoff, sorted({c["file_path"] for c in candidates})) if strict else (project_id,)
        )
        rows = cursor.fetchall()

        now = cutoff
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        if metadata is not None:
            metadata["available"] = bool(rows)
        # file_path -> list of per-commit entries, each usable to score any
        # candidate function in that file.
        file_commit_entries: Dict[str, List[Dict[str, Any]]] = {}

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
            time_decay = math.exp(-mu_decay * delta_days)

            # Topical relevance from commit message/diff text, independent
            # of which exact lines changed.
            message_lower = message.lower()
            diff_lower = diff.lower()
            term_bonus = 0.0
            for term in bug_search_terms:
                term_lower = term.lower()
                if term_lower in message_lower:
                    term_bonus += 0.4
                if term_lower in diff_lower:
                    term_bonus += 0.3

            hunks = parse_diff_hunks(diff)

            file_commit_entries.setdefault(file_path, []).append({
                "hunks": hunks,
                "term_bonus": term_bonus,
                "time_decay": time_decay,
                "latest_commit": commit_hash[:8],
                "revision": commit_hash,
            })

            # File-level relevance, used only for the evidence commits shown
            # to the LLM/UI - independent of per-candidate function scoring.
            file_r_v = min(1.0, 0.3 + term_bonus)
            if file_r_v > 0.4 and len(git_evidence_commits) < 5:
                git_evidence_commits.append({
                    "hash": commit_hash[:8],
                    "author": author,
                    "date": committed_at.strftime("%Y-%m-%d"),
                    "message": message,
                    "file_path": file_path,
                    "diff": diff[:500]
                })

        # Assign git_score to each candidate based on function-level overlap
        # with that file's commits: a direct hit (commit's hunk overlaps
        # this exact function) scores higher than same-file-but-elsewhere,
        # which scores higher than the file never being touched at all.
        for c in candidates:
            fp = c.get("file_path", "")
            start_line = c.get("start_line", 0) or 0
            end_line = c.get("end_line", 0) or 0
            entries = file_commit_entries.get(fp, [])

            best_score = None
            best_commit = None
            for entry in entries:
                # Historic coordinates cannot be equated to the current snapshot.
                aligned = not strict or entry["revision"] == aligned_revision
                direct_hit = aligned and hunks_overlap_range(entry["hunks"], start_line, end_line)
                base = 0.3 if direct_hit else 0.15
                r_v = min(1.0, base + entry["term_bonus"])
                t_score = round(r_v * entry["time_decay"], 4)
                if best_score is None or t_score > best_score:
                    best_score = t_score
                    best_commit = entry["latest_commit"]

            if best_score is not None:
                c["git_score"] = best_score
                c["latest_commit"] = best_commit
            else:
                c["git_score"] = 0.0 if strict else 0.1
                c["latest_commit"] = "N/A"

    except Exception as e:
        if strict:
            raise
        print(f"Git temporal scoring warning: {e}")
        for c in candidates:
            c["git_score"] = 0.1
            c["latest_commit"] = "N/A"
    finally:
        cursor.close()
        if connection is None:
            conn.close()

    return candidates, git_evidence_commits
