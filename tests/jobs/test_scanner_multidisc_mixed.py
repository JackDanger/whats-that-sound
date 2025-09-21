from pathlib import Path

from src.jobs import SQLiteJobStore
from src.jobs.scanner import perform_scan


def _fixture_path(*parts: str) -> Path:
    base = Path(__file__).resolve().parents[1] / "fixtures" / "src_dir"
    return base.joinpath(*parts)


def test_scanner_selects_parent_for_mixed_raditude(tmp_path: Path):
    # Use real fixture with: 10 root tracks, CD1 artwork, CD2 with 4 tracks
    base = _fixture_path("Weezer", "2009 - Raditude")

    store = SQLiteJobStore(db_path=str(tmp_path / "jobs.sqlite"))
    perform_scan(store, base.parent)

    with store._connect() as conn:  # type: ignore
        rows = conn.execute("SELECT folder_path, status FROM jobs").fetchall()
    paths = [r[0] for r in rows]
    assert str(base) in paths
    assert str(base / "CD2") not in paths


def test_scanner_enqueues_artist_collection_children_for_acdc(tmp_path: Path):
    # AC-DC folder contains many album subfolders with tracks
    artist_root = _fixture_path("AC-DC")

    store = SQLiteJobStore(db_path=str(tmp_path / "jobs.sqlite"))
    perform_scan(store, artist_root.parent)

    with store._connect() as conn:  # type: ignore
        rows = conn.execute("SELECT folder_path, status FROM jobs").fetchall()
    paths = {Path(r[0]) for r in rows}

    # Parent artist folder should not be enqueued; many child albums should be
    assert artist_root not in paths
    # Sanity: at least a handful of album subfolders were enqueued
    children = [p for p in artist_root.iterdir() if p.is_dir()]
    assert any(child in paths for child in children)