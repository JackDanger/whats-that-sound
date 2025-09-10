from pathlib import Path
from typing import Dict
import time
import sqlite3

from src.jobs import SQLiteJobStore


def make_store(tmp_path: Path) -> SQLiteJobStore:
    return SQLiteJobStore(db_path=str(tmp_path / "jobs.sqlite"))


def test_enqueue_and_counts(tmp_path: Path):
    store = make_store(tmp_path)
    folder = tmp_path / "album1"
    folder.mkdir()
    job_id = store.enqueue(folder, {"meta": 1})
    assert isinstance(job_id, int)
    counts = store.counts()
    assert counts.get("queued", 0) == 1
    assert counts.get("analyzing", 0) == 0
    assert counts.get("ready", 0) == 0


def test_claim_moves_to_analyzing(tmp_path: Path):
    store = make_store(tmp_path)
    folder = tmp_path / "album2"
    folder.mkdir()
    store.enqueue(folder, {"meta": 2})
    claimed = store.claim_queued_for_analysis()
    assert claimed is not None
    counts = store.counts()
    assert counts.get("queued", 0) == 0
    assert counts.get("analyzing", 0) == 1


def test_approve_and_fetch_ready(tmp_path: Path):
    store = make_store(tmp_path)
    folder = tmp_path / "album3"
    folder.mkdir()
    job_id = store.enqueue(folder, {"meta": 3})
    store.claim_queued_for_analysis()  # -> analyzing
    store.approve(job_id, {"proposal": {"artist": "A"}})
    counts = store.counts()
    assert counts.get("ready", 0) == 1
    ready = store.fetch_ready(limit=10)
    assert any(fp == str(folder) for _, fp, _ in ready)
    # get_result reads from ready
    result = store.get_result(folder)
    assert isinstance(result, dict)


def test_transition_moving_to_completed(tmp_path: Path):
    store = make_store(tmp_path)
    folder = tmp_path / "album4"
    folder.mkdir()
    job_id = store.enqueue(folder, {"meta": 4})
    store.claim_queued_for_analysis()
    store.approve(job_id, {"proposal": {"artist": "B"}})
    updated = store.update_latest_status_for_folder(folder, ["ready"], "moving")
    assert isinstance(updated, int)
    counts = store.counts()
    assert counts.get("moving", 0) == 1
    store.update_latest_status_for_folder(folder, ["moving"], "completed")
    counts = store.counts()
    assert counts.get("completed", 0) == 1


def test_reconsider_and_skip(tmp_path: Path):
    store = make_store(tmp_path)
    folder = tmp_path / "album5"
    folder.mkdir()
    job_id = store.enqueue(folder, {"meta": 5})
    store.claim_queued_for_analysis()
    store.approve(job_id, {"proposal": {"artist": "C"}})
    # Reconsider transitions back to analyzing
    store.update_latest_status_for_folder(folder, ["ready", "skipped"], "analyzing")
    counts = store.counts()
    assert counts.get("analyzing", 0) == 1
    # Skip transitions to skipped
    store.update_latest_status_for_folder(folder, ["ready", "analyzing"], "skipped")
    counts = store.counts()
    assert counts.get("skipped", 0) == 1


def test_error_state(tmp_path: Path):
    store = make_store(tmp_path)
    folder = tmp_path / "album7"
    folder.mkdir()
    job_id = store.enqueue(folder, {"meta": 7})
    store.claim_queued_for_analysis()
    store.fail(job_id, "synthetic error")
    counts = store.counts()
    assert counts.get("error", 0) == 1


def test_reset_stale_analyzing(tmp_path: Path):
    store = make_store(tmp_path)
    folder = tmp_path / "album6"
    folder.mkdir()
    store.enqueue(folder, {"meta": 6})
    store.claim_queued_for_analysis()  # analyzing with started_at set
    # Force started_at to be 5 minutes ago to ensure stale
    db_path = str(tmp_path / "jobs.sqlite")
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE jobs SET started_at=datetime('now','-300 seconds') WHERE status='analyzing' AND folder_path=?",
            (str(folder),),
        )
        conn.commit()
    reset = store.reset_stale_analyzing(max_age_seconds=0)
    assert reset >= 1
    counts = store.counts()
    assert counts.get("queued", 0) >= 1

