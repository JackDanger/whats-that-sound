from pathlib import Path
from typing import Iterable

from . import models
from .jobs import SQLiteJobStore  # type: ignore circular for type-checkers


def enqueue_scan_jobs(jobstore: SQLiteJobStore, root: Path) -> None:
    """Enqueue a single scan job for the given root directory."""
    jobstore.enqueue(root, {"type": "scan", "root": str(root)}, job_type="scan")


def perform_scan(jobstore: SQLiteJobStore, base: Path) -> None:
    """Walk immediate subdirectories of base and enqueue analyze jobs if not marked.

    Writes a ".whats-that-sound" marker in each enqueued directory to avoid duplicates.
    """
    for d in sorted([p for p in base.iterdir() if p.is_dir()]):
        marker = d / ".whats-that-sound"
        if marker.exists():
            continue
        jobstore.enqueue(d, {"folder_name": d.name}, job_type="analyze")
        try:
            marker.write_text("enqueued\n", encoding="utf-8")
        except Exception:
            pass


