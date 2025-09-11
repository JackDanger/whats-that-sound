import os
from pathlib import Path

from src.jobs import SQLiteJobStore
from src.jobs.scanner import perform_scan


def _touch(p: Path):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"x")


def test_scanner_handles_mixed_root_and_disc_subfolders_and_selects_parent(tmp_path: Path):
    # Layout:
    # root has 10 tracks, plus CD1 (art) and CD2 with 4 tracks.
    # Expect: scanner enqueues the root as a single album, not CD2.
    base = tmp_path / "Weezer" / "2009 - Raditude"
    base.mkdir(parents=True, exist_ok=True)

    # 10 root tracks
    for i in range(1, 11):
        name = f"{i:02d} - Track {i}.flac"
        _touch(base / name)

    # CD1 (only artwork)
    (base / "CD1").mkdir()
    _touch(base / "CD1" / "Folder.jpg")

    # CD2 with 4 tracks + artwork
    (base / "CD2").mkdir()
    for i in range(1, 5):
        name = f"{i:02d} - Disc2 {i}.flac"
        _touch(base / "CD2" / name)
    _touch(base / "CD2" / "Folder.jpg")

    store = SQLiteJobStore(db_path=str(tmp_path / "jobs.sqlite"))

    perform_scan(store, base.parent)

    # Verify: only the parent folder is enqueued, not the CD2 subdir
    counts = store.counts()
    assert counts.get("queued", 0) == 1
    ready = store.fetch_ready(limit=10)
    # No ready yet; just ensure the enqueued path matches base
    # Fetch from DB directly to confirm
    with store._connect() as conn:  # type: ignore
        rows = conn.execute("SELECT folder_path, status FROM jobs").fetchall()
    paths = [r[0] for r in rows]
    assert str(base) in paths
    assert not any(str(base / "CD2") == p for p in paths)

def test_scanner_handles_mixed_root_and_disc_subfolders_and_selects_disk_folders(tmp_path: Path):
    # Layout:
    # root has 10 tracks, CD1 has the same 10 tracks, CD2 has 9 tracks
    # Expect: scanner enqueues this as a multi-disc album, not a single album.
    base = tmp_path / "Weezer" / "2009 - Raditude"
    base.mkdir(parents=True, exist_ok=True)

    # 10 root tracks
    for i in range(1, 11):
        name = f"{i:02d} - Track {i}.flac"
        _touch(base / name)

    # CD1 has the same 10 tracks
    for i in range(1, 11):
        name = f"{i:02d} - Track {i}.flac"
        _touch(base / "CD1" / name)

    # CD2 with 9 tracks
    (base / "CD2").mkdir()
    for i in range(1, 10):
        name = f"{i:02d} - Disc2 {i}.flac"
        _touch(base / "CD2" / name)

    store = SQLiteJobStore(db_path=str(tmp_path / "jobs.sqlite"))

    perform_scan(store, base.parent)

    # Verify: individual disc folders are enqueued, parent is not
    with store._connect() as conn:  # type: ignore
        rows = conn.execute("SELECT folder_path, status FROM jobs").fetchall()
    paths = [r[0] for r in rows]
    assert str(base) not in paths
    assert str(base / "CD1") in paths
    assert str(base / "CD2") in paths