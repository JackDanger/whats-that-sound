"""Main music organization orchestrator."""

from pathlib import Path
from llama_cpp import Llama
from rich.console import Console

from .analyzers import DirectoryAnalyzer, StructureClassifier
from .generators import ProposalGenerator
from .organizers import FileOrganizer
from .processors import AlbumProcessor, CollectionProcessor
from .processors.background_processor import BackgroundProposalProcessor
from .trackers import ProgressTracker, StateManager
from .ui import InteractiveUI

console = Console()


class MusicOrganizer:
    """Orchestrates the music organization process using specialized components."""

    def __init__(self, model_path: Path, source_dir: Path, target_dir: Path):
        """Initialize the music organizer.

        Args:
            model_path: Path to the GGUF model file
            source_dir: Source directory with unorganized music
            target_dir: Target directory for organized music
        """
        self.source_dir = source_dir
        self.target_dir = target_dir

        # Initialize LLM
        console.print(f"[cyan]Loading model: {model_path.name}[/cyan]")
        console.print("[dim]This may take a moment...[/dim]")

        try:
            self.llm = Llama(
                model_path=str(model_path),
                n_ctx=4096,
                n_gpu_layers=-1,  # Use all GPU layers
                verbose=False,
            )
            console.print("[green]✓ Model loaded successfully![/green]")
        except Exception as e:
            console.print(f"[red]Error loading model: {e}[/red]")
            raise

        # Initialize components
        self._initialize_components()

    def _initialize_components(self):
        """Initialize all the specialized components."""
        # Core components
        self.directory_analyzer = DirectoryAnalyzer()
        self.structure_classifier = StructureClassifier(self.llm)
        self.proposal_generator = ProposalGenerator(self.llm)
        self.file_organizer = FileOrganizer(self.target_dir)
        self.progress_tracker = ProgressTracker()
        self.state_manager = StateManager()
        self.ui = InteractiveUI()

        # Background processor for LLM inference
        self.background_processor = BackgroundProposalProcessor(
            self.proposal_generator, max_prefetch=2
        )

        # Processors
        self.album_processor = AlbumProcessor(
            self.directory_analyzer,
            self.proposal_generator,
            self.file_organizer,
            self.state_manager,
            self.ui,
            self.background_processor,
        )

        self.collection_processor = CollectionProcessor(
            self.directory_analyzer,
            self.proposal_generator,
            self.file_organizer,
            self.state_manager,
            self.ui,
            self.background_processor,
        )

    def organize(self):
        """Main organization workflow with background processing."""
        try:
            # Start background processor
            self.background_processor.start()

            # Get all top-level folders
            folders = [d for d in self.source_dir.iterdir() if d.is_dir()]

            if not folders:
                console.print("[yellow]No folders found in source directory.[/yellow]")
                return

            # Filter out already organized folders
            unorganized_folders, organized_count = (
                self.state_manager.filter_unorganized_folders(folders)
            )

            if organized_count > 0:
                console.print(
                    f"[yellow]Found {organized_count} already organized folders, skipping them.[/yellow]"
                )

            if not unorganized_folders:
                console.print("[yellow]No unorganized folders found.[/yellow]")
                return

            console.print(
                f"\n[bold cyan]Found {len(unorganized_folders)} folders to process[/bold cyan]\n"
            )

            # Pre-analyze first few folders and submit background jobs
            self._prefetch_proposals(unorganized_folders)

            # Process each folder
            for idx, folder in enumerate(unorganized_folders, 1):
                try:
                    self.ui.display_progress(idx, len(unorganized_folders), folder.name)

                    # Analyze directory structure
                    console.print("\n[cyan]Analyzing directory structure...[/cyan]")
                    structure_analysis = (
                        self.directory_analyzer.analyze_directory_structure(folder)
                    )

                    if structure_analysis["total_music_files"] == 0:
                        console.print(
                            "[yellow]No music files found in this folder, skipping...[/yellow]"
                        )
                        self.progress_tracker.increment_skipped()
                        continue

                    # Display structure analysis
                    self.ui.display_structure_analysis(structure_analysis)

                    # Classify structure type
                    structure_type = (
                        self.structure_classifier.classify_directory_structure(
                            structure_analysis
                        )
                    )
                    console.print(
                        f"[cyan]Detected structure type: {structure_type}[/cyan]"
                    )

                    # Process based on structure type
                    success = self._process_folder_by_type(
                        folder, structure_type, structure_analysis
                    )

                    # Update progress
                    self.progress_tracker.increment_processed()
                    if success:
                        # The specific processors handle their own success tracking
                        pass
                    else:
                        self.progress_tracker.increment_skipped()

                    # Check for source directory changes
                    if self.background_processor.check_source_dir_changed(
                        self.source_dir
                    ):
                        console.print(
                            "[yellow]Source directory changed, re-analyzing remaining folders...[/yellow]"
                        )
                        # Re-submit background jobs for remaining folders
                        remaining_folders = unorganized_folders[idx:]
                        if remaining_folders:
                            self._prefetch_proposals(remaining_folders)

                    # Pre-submit next folder's job if available
                    if idx < len(unorganized_folders):
                        self._submit_next_job(unorganized_folders, idx)

                    console.print("\n" + "─" * 80 + "\n")

                except Exception as e:
                    console.print(f"[red]Error processing {folder.name}: {e}[/red]")
                    self.progress_tracker.increment_errors()

            # Display completion summary
            self.ui.display_completion_summary(self.progress_tracker.get_stats())

        finally:
            # Always stop background processor
            self.background_processor.stop()

    def _process_folder_by_type(
        self, folder: Path, structure_type: str, structure_analysis: dict
    ) -> bool:
        """Process a folder based on its classified structure type.

        Args:
            folder: Folder to process
            structure_type: Detected structure type
            structure_analysis: Directory structure analysis

        Returns:
            True if successfully processed, False otherwise
        """
        if structure_type == "single_album":
            success = self.album_processor.process_single_album(
                folder, structure_analysis
            )
            if success:
                # Get the proposal from the state manager for stats
                tracker_data = self.state_manager.load_tracker_data(folder)
                if tracker_data.get("proposal"):
                    self.progress_tracker.increment_successful(tracker_data["proposal"])
            return success

        elif structure_type == "multi_disc_album":
            success = self.album_processor.process_multi_disc_album(
                folder, structure_analysis
            )
            if success:
                # Get the proposal from the state manager for stats
                tracker_data = self.state_manager.load_tracker_data(folder)
                if tracker_data.get("proposal"):
                    self.progress_tracker.increment_successful(tracker_data["proposal"])
            return success

        elif structure_type == "artist_collection":
            success = self.collection_processor.process_artist_collection(
                folder, structure_analysis
            )
            if success:
                # Get the albums from the state manager for stats
                tracker_data = self.state_manager.load_tracker_data(folder)
                if tracker_data.get("albums"):
                    self.progress_tracker.add_successful_albums(tracker_data["albums"])
            return success

        else:
            console.print(f"[red]Unknown structure type: {structure_type}[/red]")
            return False

    def _prefetch_proposals(self, folders, max_jobs: int = 3):
        """Submit background jobs for the first few folders.

        Args:
            folders: List of folders to process
            max_jobs: Maximum number of jobs to submit
        """
        from .processors.background_processor import ProposalJob

        for i, folder in enumerate(folders[:max_jobs]):
            try:
                # Quick metadata extraction for background job
                metadata = self.directory_analyzer.extract_folder_metadata(folder)
                if metadata.get("total_files", 0) > 0:
                    job = ProposalJob(folder=folder, metadata=metadata)
                    success = self.background_processor.submit_job(job)
                    if success:
                        console.print(
                            f"[dim]Queued background proposal for {folder.name}[/dim]"
                        )
                    else:
                        break  # Queue full, stop submitting
            except Exception as e:
                console.print(
                    f"[yellow]Could not queue background job for {folder.name}: {e}[/yellow]"
                )

    def _submit_next_job(self, folders, current_idx: int):
        """Submit background job for the next folder to process.

        Args:
            folders: List of all folders
            current_idx: Current folder index (0-based)
        """
        from .processors.background_processor import ProposalJob

        # Submit job for folder 2-3 ahead to keep pipeline filled
        next_idx = current_idx + 2  # Submit job 2 folders ahead
        if next_idx < len(folders):
            folder = folders[next_idx]
            try:
                metadata = self.directory_analyzer.extract_folder_metadata(folder)
                if metadata.get("total_files", 0) > 0:
                    job = ProposalJob(folder=folder, metadata=metadata)
                    self.background_processor.submit_job(job)
            except Exception as e:
                console.print(
                    f"[dim]Could not queue background job for {folder.name}: {e}[/dim]"
                )
