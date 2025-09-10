from pathlib import Path
from typing import Dict

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
    assert counts.get("approved", 0) == 0


def test_claim_moves_to_analyzing(tmp_path: Path):
    store = make_store(tmp_path)
    folder = tmp_path / "album2"
    folder.mkdir()
    store.enqueue(folder, {"meta": 2})
    claimed = store.claim_next()
    assert claimed is not None
    counts = store.counts()
    assert counts.get("queued", 0) == 0
    assert counts.get("analyzing", 0) == 1


def test_approve_and_fetch_ready(tmp_path: Path):
    store = make_store(tmp_path)
    folder = tmp_path / "album3"
    folder.mkdir()
    job_id = store.enqueue(folder, {"meta": 3})
    store.claim_next()  # -> analyzing
    store.approve(job_id, {"proposal": {"artist": "A"}})
    counts = store.counts()
    assert counts.get("approved", 0) == 1
    ready = store.fetch_approved(limit=10)
    assert any(fp == str(folder) for _, fp, _ in ready)
    # get_result reads from approved
    result = store.get_result(folder)
    assert isinstance(result, dict)


def test_transition_moving_to_completed(tmp_path: Path):
    store = make_store(tmp_path)
    folder = tmp_path / "album4"
    folder.mkdir()
    job_id = store.enqueue(folder, {"meta": 4})
    store.claim_next()
    store.approve(job_id, {"proposal": {"artist": "B"}})
    updated = store.update_latest_status_for_folder(folder, ["approved"], "moving")
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
    store.claim_next()
    store.approve(job_id, {"proposal": {"artist": "C"}})
    # Reconsider transitions back to analyzing
    store.update_latest_status_for_folder(folder, ["approved", "skipped"], "analyzing")
    counts = store.counts()
    assert counts.get("analyzing", 0) == 1
    # Skip transitions to skipped
    store.update_latest_status_for_folder(folder, ["approved", "analyzing"], "skipped")
    counts = store.counts()
    assert counts.get("skipped", 0) == 1


def test_reset_stale_analyzing(tmp_path: Path):
    store = make_store(tmp_path)
    folder = tmp_path / "album6"
    folder.mkdir()
    store.enqueue(folder, {"meta": 6})
    store.claim_next()  # analyzing with started_at set
    # Using zero threshold to force reset
    reset = store.reset_stale_in_progress(max_age_seconds=0)
    assert reset >= 1
    counts = store.counts()
    assert counts.get("queued", 0) >= 1

