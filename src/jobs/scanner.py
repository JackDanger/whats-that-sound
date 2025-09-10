from pathlib import Path

from . import SQLiteJobStore  # type: ignore circular import


def enqueue_scan_jobs(jobstore: SQLiteJobStore, root: Path) -> None:
    """Enqueue a single scan job for the given root directory."""
    jobstore.enqueue(root, {"type": "scan", "root": str(root)}, job_type="scan")


def perform_scan(jobstore: SQLiteJobStore, base: Path) -> None:
    """Walk immediate subdirectories of base and enqueue analyze jobs when absent.

    Uses the job store to check if any job already exists for the folder to prevent duplicates.
    """
    for d in sorted([p for p in base.iterdir() if p.is_dir()]):
        if jobstore.has_any_for_folder(d):
            continue
        jobstore.enqueue(d, {"folder_name": d.name}, job_type="analyze")


