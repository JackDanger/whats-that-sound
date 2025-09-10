"""File organization and movement operations."""

import shutil
from pathlib import Path
from typing import Dict
import logging
from ..metadata import MetadataExtractor

logger = logging.getLogger("wts.file_organizer")


class FileOrganizer:
    """Handles actual file movement and copying operations."""

    def __init__(self, target_dir: Path):
        """Initialize the file organizer.

        Args:
            target_dir: Target directory for organized music
        """
        self.target_dir = target_dir

    def organize_folder(self, source_folder: Path, proposal: Dict) -> int:
        """Organize a folder based on the accepted proposal.

        Args:
            source_folder: Source folder to organize
            proposal: Organization proposal with artist, album, year, etc.

        Returns:
            Number of files copied
        """
        # Create target directory structure
        artist = self._sanitize_filename(proposal["artist"])
        album = self._sanitize_filename(proposal["album"])
        year = proposal.get("year", "Unknown")

        # Create directory: Artist/Album (Year)
        album_dir = self.target_dir / artist / f"{album} ({year})"
        album_dir.mkdir(parents=True, exist_ok=True)

        # Copy all music files
        copied = 0
        for ext in MetadataExtractor.SUPPORTED_FORMATS:
            # Find all files with this extension
            for file_path in source_folder.rglob(f"*{ext}"):
                try:
                    # Maintain relative structure within the album folder
                    relative_path = file_path.relative_to(source_folder)
                    target_path = album_dir / relative_path
                    target_path.parent.mkdir(parents=True, exist_ok=True)

                    shutil.copy2(file_path, target_path)
                    copied += 1
                except Exception as e:
                    logger.error(f"Error copying {file_path.name}: {e}")
        logger.info(
            f"Organized {copied} files to: {album_dir.relative_to(self.target_dir)}"
        )

        return copied

    def _sanitize_filename(self, name: str) -> str:
        """Sanitize a string for use as a filename.

        Args:
            name: Original filename

        Returns:
            Sanitized filename
        """
        # Remove or replace invalid characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            name = name.replace(char, "_")

        # Limit length
        return name[:120].strip()
