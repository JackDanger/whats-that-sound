"""Simple multiprocessing worker that processes jobs from SQLiteJobStore.

We avoid Celery to keep deployment simple (no external broker). This worker
can be spawned as a separate process and will process jobs concurrently using
threads within the process for I/O-bound inference.
"""

from __future__ import annotations

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from .jobs import SQLiteJobStore
from .generators.proposal_generator import ProposalGenerator
from .inference import InferenceProvider
from .analyzers import DirectoryAnalyzer, StructureClassifier
import logging
import os


def _process_one(jobstore: SQLiteJobStore, generator: ProposalGenerator, job_id: int, folder_path: str, metadata_json: str, user_feedback: Optional[str], artist_hint: Optional[str], job_type: str):
    import json
    from pathlib import Path

    try:
        metadata = json.loads(metadata_json)
        if job_type == "scan":
            # Scan a directory and enqueue analyze jobs for discovered album folders
            from pathlib import Path as _P
            base = _P(folder_path)
            for d in sorted([p for p in base.iterdir() if p.is_dir()]):
                if jobstore.has_any_for_folder(d):
                    continue
                # Minimal metadata; downstream analyzer will compute full metadata
                jobstore.enqueue(d, {"folder_name": d.name}, job_type="analyze")
            # Mark scan job as completed
            jobstore.update_latest_status_for_folder(base, ["analyzing"], "completed")
        else:
            result = generator.get_llm_proposal(folder_path=folder_path, metadata=metadata, user_feedback=user_feedback, artist_hint=artist_hint)
            # Mark job as ready (formerly 'approved')
            jobstore.approve(job_id, result)
    except Exception as e:
        jobstore.fail(job_id, str(e))
        raise e


def run_scan_worker(poll_seconds: int = 300):
    jobstore = SQLiteJobStore()
    while True:
        from pathlib import Path as _P
        # Enqueue analyze jobs for subdirectories if missing
        # Determine root from env (used by server startup), fallback to CWD
        root = os.getenv("WTS_SOURCE_DIR")
        if root:
            base = _P(root)
            for d in sorted([p for p in base.iterdir() if p.is_dir()]):
                if jobstore.has_any_for_folder(d):
                    continue
                jobstore.enqueue(d, {"folder_name": d.name}, job_type="analyze")
        time.sleep(poll_seconds)


def run_analyze_worker(poll_seconds: int = 10):
    jobstore = SQLiteJobStore()
    # File logging for worker
    log_dir = os.getenv("WTS_LOG_DIR")
    if log_dir:
        handler = logging.FileHandler(os.path.join(log_dir, "analyze_worker.log"), encoding="utf-8")
        logging.basicConfig(level=logging.INFO, handlers=[handler])
    provider = InferenceProvider()
    generator = ProposalGenerator(provider)
    analyzer = DirectoryAnalyzer()
    classifier = StructureClassifier(provider)
    while True:
        claimed = jobstore.claim_queued_for_analysis()
        if not claimed:
            time.sleep(poll_seconds)
            continue
        try:
            import json
            # Always re-analyze and classify for safety
            from pathlib import Path as _P
            folder_path = _P(claimed.folder_path)
            structure = analyzer.analyze_directory_structure(folder_path)
            classification = classifier.classify_directory_structure(structure)
            if classification == "artist_collection":
                # Fan out: enqueue each album subdir with artist hint, then skip this job
                for sub in structure.get("subdirectories", []):
                    album_dir = folder_path / sub.get("name", "")
                    if not album_dir.is_dir():
                        continue
                    if jobstore.has_any_for_folder(album_dir):
                        continue
                    album_meta = analyzer.extract_folder_metadata(album_dir)
                    if album_meta.get("total_files", 0) > 0:
                        jobstore.enqueue(album_dir, album_meta, artist_hint=folder_path.name, job_type="analyze")
                jobstore.update_latest_status_for_folder(folder_path, ["analyzing"], "skipped")
                continue
            elif classification in ("single_album", "multi_disc_album"):
                # Proceed to proposal generation
                metadata = analyzer.extract_folder_metadata(folder_path)
                if metadata.get("total_files", 0) == 0:
                    jobstore.update_latest_status_for_folder(folder_path, ["analyzing"], "skipped")
                    continue
                result = generator.get_llm_proposal(metadata, user_feedback=claimed.user_feedback, artist_hint=claimed.artist_hint, folder_path=str(folder_path))
                jobstore.approve(claimed.job_id, result)
            else:
                # Unknown classification; skip to avoid bad proposals
                jobstore.update_latest_status_for_folder(folder_path, ["analyzing"], "skipped")
        except Exception as e:
            jobstore.fail(claimed.job_id, str(e))


def run_move_worker(poll_seconds: int = 10):
    jobstore = SQLiteJobStore()
    from pathlib import Path as _P
    from .organizers import FileOrganizer as _FO
    # Target root from env
    target_dir = os.getenv("WTS_TARGET_DIR")
    organizer = _FO(_P(target_dir) if target_dir else _P.cwd())
    while True:
        claimed = jobstore.claim_accepted_for_move()
        if not claimed:
            time.sleep(poll_seconds)
            continue
        try:
            import json
            metadata = json.loads(claimed.metadata_json)
            # Expect proposal in metadata for move step
            proposal = metadata.get("proposal") or {}
            organizer.organize_folder(_P(claimed.folder_path), proposal)
            jobstore.update_latest_status_for_folder(_P(claimed.folder_path), ["moving"], "completed")
        except Exception as e:
            jobstore.update_latest_status_for_folder(_P(claimed.folder_path), ["moving"], "error")


if __name__ == "__main__":
    # For manual debugging, run analyze worker
    run_analyze_worker()


