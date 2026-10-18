from typing import Optional
from db.schema import get_connection


def is_repo_processed(full_name: str) -> bool:
    conn = get_connection()
    row = conn.execute(
        "SELECT 1 FROM processed_repos WHERE full_name = ? AND status = 'forked'",
        (full_name,),
    ).fetchone()
    conn.close()
    return row is not None


def mark_repo_processed(full_name: str, stars: int, language: str, license_key: str,
                        innovation_score: int, innovation_description: str,
                        fork_url: str = "", status: str = "discovered"):
    conn = get_connection()
    conn.execute("""
        INSERT OR REPLACE INTO processed_repos
        (full_name, stars, language, license_key, innovation_score, innovation_description, fork_url, status, processed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    """, (full_name, stars, language, license_key, innovation_score, innovation_description, fork_url, status))
    conn.commit()
    conn.close()


def create_run_log() -> int:
    conn = get_connection()
    cur = conn.execute("INSERT INTO run_logs (started_at) VALUES (CURRENT_TIMESTAMP)")
    run_id = cur.lastrowid or 0
    conn.commit()
    conn.close()
    return run_id


def complete_run_log(run_id: int, repos_discovered: int, repos_qualified: int,
                     forks_created: int, forks_succeeded: int, total_api_calls: int,
                     status: str = "completed", error: Optional[str] = None):
    conn = get_connection()
    conn.execute("""
        UPDATE run_logs SET
            completed_at = CURRENT_TIMESTAMP,
            repos_discovered = ?,
            repos_qualified = ?,
            forks_created = ?,
            forks_succeeded = ?,
            total_api_calls = ?,
            status = ?,
            error = ?
        WHERE id = ?
    """, (repos_discovered, repos_qualified, forks_created, forks_succeeded,
          total_api_calls, status, error, run_id))
    conn.commit()
    conn.close()


def get_forked_repos(limit: int = 50) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM processed_repos WHERE status = 'forked' ORDER BY processed_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_recent_runs(limit: int = 10) -> list[dict]:
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM run_logs ORDER BY started_at DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(row) for row in rows]
