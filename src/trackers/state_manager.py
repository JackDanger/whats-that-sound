"""State management for music organization."""
import logging
import json
from pathlib import Path
from typing import Dict, List


logger = logging.getLogger("wts.state_manager")

class StateManager:
    """Manages organization state and tracker files."""

    def __init__(self):
        """Initialize the state manager."""
        pass


    def is_already_organized(self, folder: Path) -> bool:
        """Check if a folder has already been organized.

        Args:
            folder: Folder to check

        Returns:
            True if folder is already organized
        """
        tracker_file = folder / ".whats-that-sound"
        return tracker_file.exists()

    def filter_unorganized_folders(self, folders: List[Path]) -> tuple[List[Path], int]:
        """Filter out already organized folders.

        Args:
            folders: List of folders to filter

        Returns:
            Tuple of (unorganized_folders, organized_count)
        """
        unorganized_folders = []
        organized_count = 0

        for folder in folders:
            if self.is_already_organized(folder):
                organized_count += 1
                logger.info(f"Skipping {folder.name} (already organized)")
            else:
                unorganized_folders.append(folder)

        return unorganized_folders, organized_count

    def save_proposal_tracker(self, source_folder: Path, proposal: Dict):
        """Save the accepted proposal to a tracker file.

        Args:
            source_folder: Source folder that was organized
            proposal: The accepted proposal
        """
        tracker_file = source_folder / ".whats-that-sound"

        tracker_data = {
            "proposal": proposal,
            "folder_name": source_folder.name,
            "organized_timestamp": str(Path().absolute()),
        }

        try:
            with open(tracker_file, "w", encoding="utf-8") as f:
                json.dump(tracker_data, f, indent=2, ensure_ascii=False)
            logger.info(
                f"[dim]Saved organization record to {tracker_file.name}[/dim]"
            )
        except Exception as e:
            logger.error(f"Warning: Could not save tracker file: {e}")

    def save_collection_tracker(self, folder: Path, albums: List[Dict]):
        """Save tracker file for an artist collection.

        Args:
            folder: Artist collection folder
            albums: List of successfully organized albums
        """
        tracker_file = folder / ".whats-that-sound"

        tracker_data = {
            "collection_type": "artist_collection",
            "folder_name": folder.name,
            "albums": albums,
            "organized_timestamp": str(Path().absolute()),
        }

        try:
            with open(tracker_file, "w", encoding="utf-8") as f:
                json.dump(tracker_data, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved collection record to {tracker_file.name}")
        except Exception as e:
            logger.error(f"Warning: Could not save tracker file: {e}")

    def load_tracker_data(self, folder: Path) -> Dict:
        """Load tracker data for a folder.

        Args:
            folder: Folder to load tracker data for

        Returns:
            Dictionary containing tracker data or empty dict if not found
        """
        tracker_file = folder / ".whats-that-sound"

        if not tracker_file.exists():
            return {}

        try:
            with open(tracker_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading tracker file: {e}")
            return {}
