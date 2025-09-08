import os
from pathlib import Path

from src.jobs import SQLiteJobStore


def test_jobstore_enqueue_and_complete(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("WTS_DB_PATH", db_path)
    store = SQLiteJobStore()

    folder = tmp_path / "album"
    folder.mkdir()
    metadata = {"folder_name": "album", "total_files": 1, "files": [], "analysis": {}}

    job_id = store.enqueue(folder, metadata)
    assert isinstance(job_id, int)

    claim = store.claim_next()
    assert claim is not None
    assert claim.job_id == job_id

    result = {"artist": "A", "album": "B", "year": "2024", "release_type": "Album"}
    store.complete(job_id, result)

    got = store.get_result(folder)
    assert got == result


