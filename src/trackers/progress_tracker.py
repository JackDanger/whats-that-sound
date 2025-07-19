"""Progress tracking for music organization."""

from typing import Dict, List


class ProgressTracker:
    """Tracks progress and statistics during music organization."""

    def __init__(self):
        """Initialize the progress tracker."""
        self.stats = {
            "total_processed": 0,
            "successful": 0,
            "skipped": 0,
            "errors": 0,
            "organized_albums": [],
        }

    def increment_processed(self):
        """Increment the total processed counter."""
        self.stats["total_processed"] += 1

    def increment_successful(self, proposal: Dict):
        """Increment successful counter and add album.

        Args:
            proposal: The successful organization proposal
        """
        self.stats["successful"] += 1
        self.stats["organized_albums"].append(proposal)

    def increment_skipped(self):
        """Increment the skipped counter."""
        self.stats["skipped"] += 1

    def increment_errors(self):
        """Increment the errors counter."""
        self.stats["errors"] += 1

    def add_successful_albums(self, albums: List[Dict]):
        """Add multiple successful albums to the stats.

        Args:
            albums: List of successful album proposals
        """
        self.stats["successful"] += len(albums)
        self.stats["organized_albums"].extend(albums)

    def get_stats(self) -> Dict:
        """Get current statistics.

        Returns:
            Dictionary containing current stats
        """
        return self.stats.copy()

    def reset(self):
        """Reset all statistics to zero."""
        self.stats = {
            "total_processed": 0,
            "successful": 0,
            "skipped": 0,
            "errors": 0,
            "organized_albums": [],
        }
