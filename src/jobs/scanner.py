from pathlib import Path
import os

import logging

from ..metadata import MetadataExtractor  # type: ignore

from . import SQLiteJobStore  # type: ignore circular import


logger = logging.getLogger("wts.jobs.scanner")


def enqueue_scan_jobs(jobstore: SQLiteJobStore, root: Path) -> None:
    """Enqueue a single scan job for the given root directory."""
    jobstore.enqueue(root, {"type": "scan", "root": str(root)}, job_type="scan")


IGNORE_DIR_NAMES = {
    "scans",
    "scan",
    "artwork",
    "covers",
    "cover",
    "booklet",
    "extras",
    "logs",
    "log",
}


def _dir_has_music_anywhere(dir_path: Path) -> bool:
    for root, _dirs, files in os.walk(dir_path, topdown=True, onerror=lambda e: None):
        # prune ignored directories
        _dirs[:] = [d for d in _dirs if d.lower() not in IGNORE_DIR_NAMES]
        for name in files:
            if Path(name).suffix.lower() in MetadataExtractor.SUPPORTED_FORMATS:
                return True
    return False


def _dir_has_music_direct(dir_path: Path) -> bool:
    for entry in dir_path.iterdir():
        if entry.is_file() and entry.suffix.lower() in MetadataExtractor.SUPPORTED_FORMATS:
            return True
    return False


def _looks_like_disc_folder(name: str) -> bool:
    lowered = name.lower()
    if lowered in IGNORE_DIR_NAMES:
        return False
    return (
        lowered.startswith("cd")
        or lowered.startswith("disc")
        or lowered.startswith("disk")
        or lowered.startswith("vol")
        or lowered.startswith("volume")
    )


def perform_scan(jobstore: SQLiteJobStore, base: Path) -> None:
    """Scan base for albums and enqueue analyze jobs.

    Rules:
    - If a child folder has music files directly, enqueue that folder (album).
    - If a child folder has no direct music but contains disc-like subdirs (cd1/cd2), enqueue the child (multi-disc album).
    - Else, if a child folder has subfolders with music, treat it as an artist collection and enqueue each album subfolder with artist_hint=child.name.
    """
    for artist_or_album in sorted([p for p in base.iterdir() if p.is_dir()]):
        try:
            logger.info(f"Scanning {artist_or_album}")
            # Already tracked?
            if jobstore.has_any_for_folder(artist_or_album):
                logger.info(f"Already tracked {artist_or_album}")
                continue

            # Inspect subdirectories and direct music presence
            subdirs = [d for d in artist_or_album.iterdir() if d.is_dir() and d.name.lower() not in IGNORE_DIR_NAMES]
            direct_music = _dir_has_music_direct(artist_or_album)
            # Multi-disc heuristic (stricter + mixed case handling)
            if subdirs:
                disc_like = [d for d in subdirs if _looks_like_disc_folder(d.name)]
                disc_like_count = len(disc_like)
                if direct_music and disc_like_count >= 1:
                    # If root has more tracks than combined disc subfolders, treat as single album
                    root_tracks = 0
                    try:
                        for entry in artist_or_album.iterdir():
                            if entry.is_file() and entry.suffix.lower() in MetadataExtractor.SUPPORTED_FORMATS:
                                root_tracks += 1
                    except Exception:
                        pass
                    disc_tracks = 0
                    for d in disc_like:
                        try:
                            for _r, _ds, files in os.walk(d, topdown=True, onerror=lambda e: None):
                                for name in files:
                                    if Path(name).suffix.lower() in MetadataExtractor.SUPPORTED_FORMATS:
                                        disc_tracks += 1
                        except Exception:
                            continue
                    # If disc subfolders clearly dominate and there are at least 2 disc-like subdirs,
                    # enqueue each disc folder (not the parent) to capture all files explicitly
                    if disc_like_count >= 2 and disc_tracks > root_tracks and disc_like_count >= max(2, int(0.5 * len(subdirs))):
                        for d in sorted(disc_like):
                            if jobstore.has_any_for_folder(d):
                                continue
                            jobstore.enqueue(d, {"folder_name": d.name}, artist_hint=artist_or_album.name, job_type="analyze")
                        continue
                    # Otherwise favor the parent as a single album (root tracks dominate or not enough disc-like subdirs)
                    jobstore.enqueue(artist_or_album, {"folder_name": artist_or_album.name}, job_type="analyze")
                    continue
                elif not direct_music and disc_like_count >= 2 and disc_like_count >= max(1, int(0.5 * len(subdirs))):
                    jobstore.enqueue(artist_or_album, {"folder_name": artist_or_album.name}, job_type="analyze")
                    continue

            # If there is direct music and no disc-like pattern, treat as single album at parent
            if direct_music and (not subdirs or all(not _looks_like_disc_folder(d.name) for d in subdirs)):
                jobstore.enqueue(artist_or_album, {"folder_name": artist_or_album.name}, job_type="analyze")
                continue

            logger.info(f"Enqueuing {artist_or_album} as artist collection")
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


