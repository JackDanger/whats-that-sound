"""Processors for album-type structures."""

from pathlib import Path
from typing import Dict
 

from ..analyzers import DirectoryAnalyzer
from ..organizers import FileOrganizer
from ..trackers import StateManager
from ..ui import InteractiveUI
from ..jobs import SQLiteJobStore

 


class AlbumProcessor:
    """Processes single albums and multi-disc albums."""

    def __init__(
        self,
        directory_analyzer: DirectoryAnalyzer,
        file_organizer: FileOrganizer,
        state_manager: StateManager,
        ui: InteractiveUI,
    ):
        """Initialize the album processor.

        Args:
            directory_analyzer: DirectoryAnalyzer instance
            file_organizer: FileOrganizer instance
            state_manager: StateManager instance
            ui: InteractiveUI instance
        """
        self.directory_analyzer = directory_analyzer
        self.file_organizer = file_organizer
        self.state_manager = state_manager
        self.ui = ui
        self.jobstore = SQLiteJobStore()

    def process_single_album(self, folder: Path, structure_analysis: Dict) -> bool:
        """Process a single album directory.

        Args:
            folder: Album folder to process
            structure_analysis: Directory structure analysis

        Returns:
            True if successfully processed, False otherwise
        """
        console.print("[cyan]Processing as single album...[/cyan]")

        # Extract metadata from the entire folder
        metadata = self.directory_analyzer.extract_folder_metadata(folder)

        if metadata.get("total_files", 0) == 0:
            return False

        return self._process_album_interactive(folder, metadata)

    def process_multi_disc_album(self, folder: Path, structure_analysis: Dict) -> bool:
        """Process a multi-disc album directory.

        Args:
            folder: Multi-disc album folder to process
            structure_analysis: Directory structure analysis

        Returns:
            True if successfully processed, False otherwise
        """
        console.print("[cyan]Processing as multi-disc album...[/cyan]")

        # Extract metadata from the entire folder (including all discs)
        metadata = self.directory_analyzer.extract_folder_metadata(folder)

        if metadata.get("total_files", 0) == 0:
            return False

        return self._process_album_interactive(folder, metadata)

    def _process_album_interactive(self, folder: Path, metadata: Dict) -> bool:
        """Handle interactive processing for an album.

        Args:
            folder: Album folder
            metadata: Extracted metadata

        Returns:
            True if successfully processed, False otherwise
        """
        # Display folder info
        self.ui.display_folder_info(metadata)
        self.ui.display_file_samples(metadata.get("files", []))

        # Get LLM proposal from background worker via job store
        proposal = self._get_proposal(folder, metadata)

        # Interactive loop for user feedback
        while True:
            self.ui.display_llm_proposal(proposal)
            feedback = self.ui.get_user_feedback(proposal)

            if feedback["action"] == "accept":
                # Save proposal to tracker file before organizing
                self.state_manager.save_proposal_tracker(folder, feedback["proposal"])

                # Organize the files
                self.file_organizer.organize_folder(folder, feedback["proposal"])
                return True

            elif feedback["action"] == "reconsider":
                # Request a new background proposal with user feedback
                proposal = self._get_proposal(
                    folder, metadata, user_feedback=feedback.get("feedback")
                )

            elif feedback["action"] == "skip":
                console.print("[yellow]Skipping this folder...[/yellow]")
                return False

            elif feedback["action"] == "cancel":
                console.print("[red]Cancelling organization...[/red]")
                return False

    def _get_proposal(
        self,
        folder: Path,
        metadata: Dict,
        user_feedback: str = None,
        artist_hint: str = None,
    ) -> Dict:
        """Get proposal produced by the single background worker via the job store.

        If no result exists yet, enqueue an analyze job and wait for the result.
        """
        # Return existing ready result if present
        existing = self.jobstore.get_result(folder)
        if existing and not user_feedback:
            console.print("[green]Using background worker proposal![/green]")
            return existing

        # Enqueue analyze job if none active
        if not self.jobstore.has_any_for_folder(folder):
            self.jobstore.enqueue(folder, metadata, user_feedback=user_feedback, artist_hint=artist_hint, job_type="analyze")
            console.print("[cyan]Enqueued analyze job for background processing...[/cyan]")

        # Wait for result from background worker
        result = self.jobstore.wait_for_result(folder, timeout=300.0)
        if not result:
            raise RuntimeError("Timed out waiting for background proposal. Ensure analyze worker is running.")
        console.print("[green]Background proposal ready![/green]")
        return result
