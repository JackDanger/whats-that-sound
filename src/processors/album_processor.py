"""Processors for album-type structures."""

from pathlib import Path
from typing import Dict
from rich.console import Console

from ..analyzers import DirectoryAnalyzer
from ..generators import ProposalGenerator
from ..organizers import FileOrganizer
from ..trackers import StateManager
from ..ui import InteractiveUI

console = Console()


class AlbumProcessor:
    """Processes single albums and multi-disc albums."""

    def __init__(
        self,
        directory_analyzer: DirectoryAnalyzer,
        proposal_generator: ProposalGenerator,
        file_organizer: FileOrganizer,
        state_manager: StateManager,
        ui: InteractiveUI,
        background_processor=None,
    ):
        """Initialize the album processor.

        Args:
            directory_analyzer: DirectoryAnalyzer instance
            proposal_generator: ProposalGenerator instance
            file_organizer: FileOrganizer instance
            state_manager: StateManager instance
            ui: InteractiveUI instance
            background_processor: BackgroundProposalProcessor instance (optional)
        """
        self.directory_analyzer = directory_analyzer
        self.proposal_generator = proposal_generator
        self.file_organizer = file_organizer
        self.state_manager = state_manager
        self.ui = ui
        self.background_processor = background_processor

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

        # Get LLM proposal (try background first, fallback to synchronous)
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
                # Get new proposal with user feedback (always synchronous for reconsideration)
                proposal = self.proposal_generator.get_llm_proposal(
                    metadata, feedback.get("feedback")
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
        """Get proposal using background processor if available, otherwise fallback to sync.

        Args:
            folder: Folder being processed
            metadata: Folder metadata
            user_feedback: Optional user feedback for reconsideration
            artist_hint: Optional artist hint

        Returns:
            Proposal dictionary
        """
        if self.background_processor and not user_feedback:
            # Try to get from background processor first
            job_id = str(folder)
            console.print("[cyan]Checking for background proposal...[/cyan]")

            result = self.background_processor.get_proposal(job_id)
            if result:
                if result.error:
                    console.print(
                        f"[yellow]Background proposal failed: {result.error}[/yellow]"
                    )
                    console.print("[cyan]Generating proposal synchronously...[/cyan]")
                    return self.proposal_generator.get_llm_proposal(
                        metadata, user_feedback, artist_hint
                    )
                else:
                    console.print("[green]Using background proposal![/green]")
                    return result.proposal
            else:
                # Not ready yet, wait a bit longer or fallback
                console.print("[cyan]Waiting for background proposal...[/cyan]")
                result = self.background_processor.wait_for_proposal(
                    job_id, timeout=10.0
                )
                if result and not result.error:
                    console.print("[green]Background proposal ready![/green]")
                    return result.proposal
                else:
                    console.print(
                        "[yellow]Background proposal not ready, generating synchronously...[/yellow]"
                    )

        # Fallback to synchronous generation
        return self.proposal_generator.get_llm_proposal(
            metadata, user_feedback, artist_hint
        )
