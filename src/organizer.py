"""Main music organization orchestrator."""

from pathlib import Path
from llama_cpp import Llama
from rich.console import Console

from .analyzers import DirectoryAnalyzer, StructureClassifier
from .generators import ProposalGenerator
from .organizers import FileOrganizer
from .processors import AlbumProcessor, CollectionProcessor
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

        # Processors
        self.album_processor = AlbumProcessor(
            self.directory_analyzer,
            self.proposal_generator,
            self.file_organizer,
            self.state_manager,
            self.ui,
        )

        self.collection_processor = CollectionProcessor(
            self.directory_analyzer,
            self.proposal_generator,
            self.file_organizer,
            self.state_manager,
            self.ui,
        )

    def organize(self):
        """Main organization workflow - now much simpler!"""
        # Get all top-level folders
        folders = [d for d in self.source_dir.iterdir() if d.is_dir()]

        if not folders:
            console.print("[yellow]No folders found in source directory.[/yellow]")
            return

        # Filter out already organized folders
        unorganized_folders, organized_count = self.state_manager.filter_unorganized_folders(folders)

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

        # Process each folder
        for idx, folder in enumerate(unorganized_folders, 1):
            try:
                self.ui.display_progress(idx, len(unorganized_folders), folder.name)

                # Analyze directory structure
                console.print("\n[cyan]Analyzing directory structure...[/cyan]")
                structure_analysis = self.directory_analyzer.analyze_directory_structure(folder)

                if structure_analysis["total_music_files"] == 0:
                    console.print(
                        "[yellow]No music files found in this folder, skipping...[/yellow]"
                    )
                    self.progress_tracker.increment_skipped()
                    continue

                # Display structure analysis
                self.ui.display_structure_analysis(structure_analysis)

                # Classify structure type
                structure_type = self.structure_classifier.classify_directory_structure(structure_analysis)
                console.print(f"[cyan]Detected structure type: {structure_type}[/cyan]")

                # Process based on structure type
                success = self._process_folder_by_type(folder, structure_type, structure_analysis)

                # Update progress
                self.progress_tracker.increment_processed()
                if success:
                    # The specific processors handle their own success tracking
                    pass
                else:
                    self.progress_tracker.increment_skipped()

                console.print("\n" + "─" * 80 + "\n")

            except Exception as e:
                console.print(f"[red]Error processing {folder.name}: {e}[/red]")
                self.progress_tracker.increment_errors()

        # Display completion summary
        self.ui.display_completion_summary(self.progress_tracker.get_stats())

    def _process_folder_by_type(self, folder: Path, structure_type: str, structure_analysis: dict) -> bool:
        """Process a folder based on its classified structure type.
        
        Args:
            folder: Folder to process
            structure_type: Detected structure type
            structure_analysis: Directory structure analysis
            
        Returns:
            True if successfully processed, False otherwise
        """
        if structure_type == "single_album":
            success = self.album_processor.process_single_album(folder, structure_analysis)
            if success:
                # Get the proposal from the state manager for stats
                tracker_data = self.state_manager.load_tracker_data(folder)
                if tracker_data.get("proposal"):
                    self.progress_tracker.increment_successful(tracker_data["proposal"])
            return success

        elif structure_type == "multi_disc_album":
            success = self.album_processor.process_multi_disc_album(folder, structure_analysis)
            if success:
                # Get the proposal from the state manager for stats
                tracker_data = self.state_manager.load_tracker_data(folder)
                if tracker_data.get("proposal"):
                    self.progress_tracker.increment_successful(tracker_data["proposal"])
            return success

        elif structure_type == "artist_collection":
            success = self.collection_processor.process_artist_collection(folder, structure_analysis)
            if success:
                # Get the albums from the state manager for stats
                tracker_data = self.state_manager.load_tracker_data(folder)
                if tracker_data.get("albums"):
                    self.progress_tracker.add_successful_albums(tracker_data["albums"])
            return success

        else:
            console.print(f"[red]Unknown structure type: {structure_type}[/red]")
            return False
