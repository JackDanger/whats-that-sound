"""SQLite-backed job store for background proposal generation.

Designed for single-host usage. Safe across processes via SQLite locks.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


DEFAULT_DB = os.getenv("WTS_DB_PATH", str(Path.cwd() / "whats_that_sound.db"))


@dataclass
class Job:
    job_id: int
    folder_path: str
    metadata_json: str
    user_feedback: Optional[str]
    artist_hint: Optional[str]
    status: str


class SQLiteJobStore:
    def __init__(self, db_path: str = DEFAULT_DB) -> None:
        self.db_path = db_path
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30, isolation_level=None)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  folder_path TEXT NOT NULL,
                  metadata_json TEXT NOT NULL,
                  user_feedback TEXT,
                  artist_hint TEXT,
                  status TEXT NOT NULL DEFAULT 'queued',
                  error TEXT,
                  result_json TEXT,
                  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                  started_at DATETIME,
                  completed_at DATETIME
                );
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_jobs_folder ON jobs(folder_path);"
            )

    def enqueue(self, folder: Path, metadata: Dict[str, Any], user_feedback: Optional[str] = None, artist_hint: Optional[str] = None) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO jobs(folder_path, metadata_json, user_feedback, artist_hint)
                VALUES (?, ?, ?, ?)
                """,
                (
                    str(folder),
                    json.dumps(metadata),
                    user_feedback,
                    artist_hint,
                ),
            )
            return int(cur.lastrowid)

    def claim_next(self) -> Optional[Job]:
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE;")
            row = conn.execute(
                "SELECT id, folder_path, metadata_json, user_feedback, artist_hint, status FROM jobs WHERE status = 'queued' ORDER BY id LIMIT 1"
            ).fetchone()
            if not row:
                conn.execute("COMMIT;")
                return None
            job_id = row[0]
            conn.execute(
                "UPDATE jobs SET status='in_progress', started_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (job_id,),
            )
            conn.execute("COMMIT;")
            return Job(*row)

    def complete(self, job_id: int, result: Dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE jobs SET status='completed', result_json=?, completed_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (json.dumps(result), job_id),
            )

    def fail(self, job_id: int, error: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE jobs SET status='failed', error=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (error, job_id),
            )

    def get_result(self, folder: Path) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT result_json FROM jobs WHERE folder_path=? AND status='completed' ORDER BY completed_at DESC LIMIT 1",
                (str(folder),),
            ).fetchone()
            if not row or not row[0]:
                return None
            try:
                return json.loads(row[0])
            except Exception:
                return None

    def counts(self) -> Dict[str, int]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT status, COUNT(1) FROM jobs GROUP BY status"
            ).fetchall()
            result = {"queued": 0, "in_progress": 0, "completed": 0, "failed": 0}
            for status, count in rows:
                result[status] = count
            return result

    def wait_for_result(self, folder: Path, timeout: float = 10.0, poll_interval: float = 0.25) -> Optional[Dict[str, Any]]:
        deadline = time.time() + timeout
        while time.time() < deadline:
            res = self.get_result(folder)
            if res is not None:
                return res
            time.sleep(poll_interval)
        return None


