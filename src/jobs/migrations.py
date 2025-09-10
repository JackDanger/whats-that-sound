import sqlite3


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          folder_path TEXT NOT NULL,
          metadata_json TEXT NOT NULL,
          user_feedback TEXT,
          artist_hint TEXT,
          status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','analyzing','ready','accepted','moving','skipped','completed','error')),
          job_type TEXT NOT NULL DEFAULT 'analyze',
          error TEXT,
          result_json TEXT,
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
          updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
          started_at DATETIME,
          completed_at DATETIME
        );
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_folder ON jobs(folder_path);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_type ON jobs(job_type);")
    # Prevent duplicate active jobs for same folder (allow multiple historical completed/skipped/error)
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_jobs_unique_active ON jobs(folder_path) WHERE status IN ('queued','analyzing','ready','accepted','moving');"
    )


def migrate_legacy_statuses(conn: sqlite3.Connection) -> None:
    # No legacy migrations in a simplified, fresh system.
    return None


