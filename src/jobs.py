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

    def has_any_for_folder(self, folder: Path, statuses: Optional[List[str]] = None) -> bool:
        statuses = statuses or ["queued", "in_progress", "completed"]
        q_marks = ",".join(["?"] * len(statuses))
        with self._connect() as conn:
            row = conn.execute(
                f"SELECT 1 FROM jobs WHERE folder_path=? AND status IN ({q_marks}) LIMIT 1",
                (str(folder), *statuses),
            ).fetchone()
            return row is not None

    def claim_next(self) -> Optional[Job]:
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE;")
            row = conn.execute(
                "SELECT id, folder_path, metadata_json, user_feedback, artist_hint, status FROM jobs WHERE status IN ('queued','analyzing') ORDER BY id LIMIT 1"
            ).fetchone()
            if not row:
                conn.execute("COMMIT;")
                return None
            job_id = row[0]
            # Move to analyzing if coming from queued
            if row[5] != 'analyzing':
                conn.execute(
                    "UPDATE jobs SET status='analyzing', started_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (job_id,),
                )
            conn.execute("COMMIT;")
            return Job(*row)

    def approve(self, job_id: int, result: Dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE jobs SET status='approved', result_json=?, completed_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (json.dumps(result), job_id),
            )

    def fail(self, job_id: int, error: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE jobs SET status='skipped', error=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (error, job_id),
            )

    def get_result(self, folder: Path) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT result_json FROM jobs WHERE folder_path=? AND status='approved' ORDER BY completed_at DESC LIMIT 1",
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
            result = {"queued": 0, "analyzing": 0, "approved": 0, "moving": 0, "skipped": 0, "completed": 0}
            for status, count in rows:
                result[status] = count
            return result

    def reset_stale_in_progress(self, max_age_seconds: int = 300) -> int:
        """Re-queue in_progress jobs that are likely orphaned.

        Returns number of rows updated.
        """
        with self._connect() as conn:
            cur = conn.execute(
                """
                UPDATE jobs
                SET status='queued', updated_at=CURRENT_TIMESTAMP, started_at=NULL
                WHERE status='analyzing' AND started_at IS NOT NULL
                  AND (strftime('%s','now') - strftime('%s', started_at)) > ?
                """,
                (max_age_seconds,),
            )
            return cur.rowcount or 0

    def wait_for_result(self, folder: Path, timeout: float = 10.0, poll_interval: float = 0.25) -> Optional[Dict[str, Any]]:
        deadline = time.time() + timeout
        while time.time() < deadline:
            res = self.get_result(folder)
            if res is not None:
                return res
            time.sleep(poll_interval)
        return None


    def fetch_approved(self, limit: int = 10) -> List[Tuple[int, str, Dict[str, Any]]]:
        """Fetch recently approved jobs (ready for decision).

        Returns list of (job_id, folder_path, result_dict)
        """
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, folder_path, result_json FROM jobs WHERE status='approved' ORDER BY completed_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            out: List[Tuple[int, str, Dict[str, Any]]] = []
            for job_id, folder_path, result_json in rows:
                try:
                    result = json.loads(result_json) if result_json else {}
                except Exception:
                    result = {}
                out.append((int(job_id), folder_path, result))
            return out

    def delete_job(self, job_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM jobs WHERE id=?", (job_id,))

    def update_latest_status_for_folder(self, folder: Path, from_statuses: Optional[List[str]], to_status: str) -> Optional[int]:
        """Update the most recent job for a folder from one of the given from_statuses to to_status.

        Returns the job id if updated, else None.
        """
        with self._connect() as conn:
            if from_statuses:
                q_marks = ",".join(["?"] * len(from_statuses))
                row = conn.execute(
                    f"SELECT id FROM jobs WHERE folder_path=? AND status IN ({q_marks}) ORDER BY id DESC LIMIT 1",
                    (str(folder), *from_statuses),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT id FROM jobs WHERE folder_path=? ORDER BY id DESC LIMIT 1",
                    (str(folder),),
                ).fetchone()
            if not row:
                return None
            job_id = int(row[0])
            conn.execute(
                "UPDATE jobs SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (to_status, job_id),
            )
            return job_id


