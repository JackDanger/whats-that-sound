"""Processor for artist collection structures."""

from pathlib import Path
from typing import Dict, List
from rich.console import Console

from ..analyzers import DirectoryAnalyzer
from ..generators import ProposalGenerator
from ..organizers import FileOrganizer
from ..trackers import StateManager
from ..ui import InteractiveUI
from ..jobs import SQLiteJobStore

console = Console()


class CollectionProcessor:
    """Processes artist collections with multiple albums."""

    def __init__(
        self,
        directory_analyzer: DirectoryAnalyzer,
        proposal_generator: ProposalGenerator,
        file_organizer: FileOrganizer,
        state_manager: StateManager,
        ui: InteractiveUI,
        background_processor=None,
    ):
        """Initialize the collection processor.

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
        self.jobstore = SQLiteJobStore()

    def process_artist_collection(self, folder: Path, structure_analysis: Dict) -> bool:
        """Process an artist collection directory with multiple albums.

        Args:
            folder: Artist collection folder to process
            structure_analysis: Directory structure analysis

        Returns:
            True if any albums were successfully processed, False otherwise
        """
        console.print("[cyan]Processing as artist collection...[/cyan]")

        # Get the artist name from the folder
        artist_name = folder.name

        # Process each album subdirectory
        successful_albums = []

        for subdir_info in structure_analysis["subdirectories"]:
            if subdir_info["music_files"] == 0:
                continue

            album_folder = Path(subdir_info["path"])
            console.print(f"\n[cyan]Processing album: {album_folder.name}[/cyan]")

            # Extract metadata for this album
            metadata = self.directory_analyzer.extract_folder_metadata(album_folder)

            if metadata.get("total_files", 0) == 0:
                continue

            # Process this individual album
            album_result = self._process_individual_album(
                album_folder, metadata, artist_name
            )

            if album_result:
                successful_albums.append(album_result)

        if successful_albums:
            # Save tracker file for the entire collection
            self.state_manager.save_collection_tracker(folder, successful_albums)
            return True

        return False

    def _process_individual_album(
        self, album_folder: Path, metadata: Dict, artist_hint: str
    ) -> Dict:
        """Process an individual album within a collection.

        Args:
            album_folder: Album folder to process
            metadata: Extracted metadata
            artist_hint: Artist name hint from collection folder

        Returns:
            Proposal dict if successful, None if skipped/cancelled
        """
        # Display folder info
        self.ui.display_folder_info(metadata)
        self.ui.display_file_samples(metadata.get("files", []))

        # Get LLM proposal with artist hint (prefer external worker, then background)
        proposal = self._get_proposal(album_folder, metadata, artist_hint=artist_hint)

        # Interactive loop for user feedback
        while True:
            self.ui.display_llm_proposal(proposal)
            feedback = self.ui.get_user_feedback(proposal)

            if feedback["action"] == "accept":
                # Organize this album
                self.file_organizer.organize_folder(album_folder, feedback["proposal"])
                return feedback["proposal"]

            elif feedback["action"] == "reconsider":
                # Get new proposal with user feedback (always synchronous for reconsideration)
                proposal = self.proposal_generator.get_llm_proposal(
                    metadata, feedback.get("feedback"), artist_hint=artist_hint
                )

            elif feedback["action"] == "skip":
                console.print(f"[yellow]Skipping album: {album_folder.name}[/yellow]")
                return None

            elif feedback["action"] == "cancel":
                console.print("[red]Cancelling organization...[/red]")
                return None

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
        # External worker result first
        if not user_feedback:
            ext = self.jobstore.get_result(folder)
            if ext:
                console.print("[green]Using external worker proposal![/green]")
                return ext

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
