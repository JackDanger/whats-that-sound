"""Simple multiprocessing worker that processes jobs from SQLiteJobStore.

We avoid Celery to keep deployment simple (no external broker). This worker
can be spawned as a separate process and will process jobs concurrently using
threads within the process for I/O-bound inference.
"""

from __future__ import annotations

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from .jobs import SQLiteJobStore
from .generators.proposal_generator import ProposalGenerator
from .inference import InferenceProvider


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
                marker = d / ".whats-that-sound"
                if marker.exists():
                    continue
                # Minimal metadata; downstream analyzer will compute full metadata
                jobstore.enqueue(d, {"folder_name": d.name}, job_type="analyze")
                try:
                    marker.write_text("enqueued\n", encoding="utf-8")
                except Exception:
                    pass
            # Mark scan job as completed
            jobstore.update_latest_status_for_folder(base, ["analyzing"], "completed")
        else:
            result = generator.get_llm_proposal(metadata, user_feedback=user_feedback, artist_hint=artist_hint)
            # Mark job as ready (formerly 'approved')
            jobstore.approve(job_id, result)
    except Exception as e:
        jobstore.fail(job_id, str(e))
        raise e


def run_worker(max_workers: Optional[int] = None):
    jobstore = SQLiteJobStore()
    # Configure inference provider using environment
    provider = InferenceProvider()
    generator = ProposalGenerator(provider)

    max_workers = max_workers or int(os.getenv("WTS_WORKER_THREADS", "4"))

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = set()
        while True:
            # Reap completed
            done = {f for f in futures if f.done()}
            futures -= done

            # Claim and submit new jobs up to capacity
            while len(futures) < max_workers:
                claimed = jobstore.claim_next()
                if not claimed:
                    break
                f = pool.submit(
                    _process_one,
                    jobstore,
                    generator,
                    claimed.job_id,
                    claimed.folder_path,
                    claimed.metadata_json,
                    claimed.user_feedback,
                    claimed.artist_hint,
                    claimed.job_type,
                )
                futures.add(f)

            # Idle if nothing to do
            if not futures and not claimed:
                time.sleep(0.5)


if __name__ == "__main__":
    run_worker()


