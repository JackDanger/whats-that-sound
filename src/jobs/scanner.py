from pathlib import Path
import os

from ..metadata import MetadataExtractor  # type: ignore

from . import SQLiteJobStore  # type: ignore circular import


def enqueue_scan_jobs(jobstore: SQLiteJobStore, root: Path) -> None:
    """Enqueue a single scan job for the given root directory."""
    jobstore.enqueue(root, {"type": "scan", "root": str(root)}, job_type="scan")


def _dir_has_music_anywhere(dir_path: Path) -> bool:
    for root, _dirs, files in os.walk(dir_path, topdown=True, onerror=lambda e: None):
        for name in files:
            if Path(name).suffix.lower() in MetadataExtractor.SUPPORTED_FORMATS:
                return True
    return False


def _dir_has_music_direct(dir_path: Path) -> bool:
    try:
        for entry in dir_path.iterdir():
            if entry.is_file() and entry.suffix.lower() in MetadataExtractor.SUPPORTED_FORMATS:
                return True
    except Exception:
        pass
    return False


def _looks_like_disc_folder(name: str) -> bool:
    lowered = name.lower()
    return lowered.startswith("cd") or lowered.startswith("disc")


def perform_scan(jobstore: SQLiteJobStore, base: Path) -> None:
    """Scan base for albums and enqueue analyze jobs.

    Rules:
    - If a child folder has music files directly, enqueue that folder (album).
    - If a child folder has no direct music but contains disc-like subdirs (cd1/cd2), enqueue the child (multi-disc album).
    - Else, if a child folder has subfolders with music, treat it as an artist collection and enqueue each album subfolder with artist_hint=child.name.
    """
    for artist_or_album in sorted([p for p in base.iterdir() if p.is_dir()]):
        try:
            # Already tracked?
            if jobstore.has_any_for_folder(artist_or_album):
                continue

            direct_music = _dir_has_music_direct(artist_or_album)
            if direct_music:
                jobstore.enqueue(artist_or_album, {"folder_name": artist_or_album.name}, job_type="analyze")
                continue

            # Inspect subdirectories
            subdirs = [d for d in artist_or_album.iterdir() if d.is_dir()]
            # Multi-disc heuristic
            if any(_looks_like_disc_folder(d.name) for d in subdirs):
                jobstore.enqueue(artist_or_album, {"folder_name": artist_or_album.name}, job_type="analyze")
                continue

            # Artist collection heuristic: enqueue each subdir that contains music
            enqueued_any = False
            for album_dir in sorted(subdirs):
                if not _dir_has_music_anywhere(album_dir):
                    continue
                if jobstore.has_any_for_folder(album_dir):
                    continue
                jobstore.enqueue(album_dir, {"folder_name": album_dir.name}, artist_hint=artist_or_album.name, job_type="analyze")
                enqueued_any = True

            # If none enqueued but there is music somewhere below, enqueue the parent
            if not enqueued_any and _dir_has_music_anywhere(artist_or_album):
                jobstore.enqueue(artist_or_album, {"folder_name": artist_or_album.name}, job_type="analyze")
        except Exception:
            # Ignore problematic directories and continue
            continue


