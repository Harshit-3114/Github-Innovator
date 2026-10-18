import sqlite3
from core.config import settings


def get_connection() -> sqlite3.Connection:
    settings.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(settings.DB_PATH), timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS processed_repos (
            full_name TEXT PRIMARY KEY,
            stars INTEGER,
            language TEXT,
            license_key TEXT,
            innovation_score INTEGER,
            innovation_description TEXT,
            fork_url TEXT,
            status TEXT DEFAULT 'discovered',
            processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS run_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            repos_discovered INTEGER DEFAULT 0,
            repos_qualified INTEGER DEFAULT 0,
            forks_created INTEGER DEFAULT 0,
            forks_succeeded INTEGER DEFAULT 0,
            total_api_calls INTEGER DEFAULT 0,
            status TEXT DEFAULT 'running',
            error TEXT
        );

        CREATE TABLE IF NOT EXISTS file_changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER,
            repo_full_name TEXT,
            file_path TEXT,
            change_type TEXT,
            validation_passed INTEGER,
            error TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (run_id) REFERENCES run_logs(id)
        );

        CREATE INDEX IF NOT EXISTS idx_processed_repos_status ON processed_repos(status);
        CREATE INDEX IF NOT EXISTS idx_run_logs_started ON run_logs(started_at);
        CREATE INDEX IF NOT EXISTS idx_processed_repos_processed_at ON processed_repos(processed_at);
    """)
    conn.commit()
    conn.close()
