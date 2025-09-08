"""Main music organization orchestrator."""

from pathlib import Path
from rich.console import Console

from .analyzers import DirectoryAnalyzer, StructureClassifier
from .generators import ProposalGenerator
from .inference import InferenceProvider
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

        # Initialize inference provider (external or local server based)
        console.print(f"[cyan]Configuring inference provider (model: {model_path.name})[/cyan]")
        self.inference = InferenceProvider()

        # Initialize components
        self._initialize_components()

    def _initialize_components(self):
        """Initialize all the specialized components."""
        # Core components
        self.directory_analyzer = DirectoryAnalyzer()
        self.structure_classifier = StructureClassifier(self.inference)
        self.proposal_generator = ProposalGenerator(self.inference)
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
        session = OrganizationSession(self)
        try:
            session.start()

            folders = FolderDiscovery(self.source_dir, self.state_manager).discover()
            if not folders:
                return

            # Aggressively prefetch proposals for all discovered folders up-front.
            try:
                self._prefetch_proposals(folders)
            except Exception:
                # Non-fatal if prefetch fails
                pass

            pipeline = ProcessingPipeline(self, folders)
            pipeline.execute()

        finally:
            session.stop()

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

    def _prefetch_proposals(self, folders, max_jobs: int = None):
        """Submit background jobs upfront to warm the pipeline.

        Strategy:
        - Quickly analyze structure heuristically.
        - If folder looks like single or multi-disc album, queue that folder.
        - If it looks like an artist collection, queue each album subdirectory with artist_hint.

        If max_jobs is None, submit for all applicable items until queue refuses.

        Args:
            folders: List of folders to process
            max_jobs: Optional explicit limit on jobs to submit
        """
        from .processors.background_processor import ProposalJob

        count = 0
        for i, folder in enumerate(folders):
            if max_jobs is not None and count >= max_jobs:
                break
            try:
                # Analyze directory structure quickly
                structure = self.directory_analyzer.analyze_directory_structure(folder)
                structure_type = self.structure_classifier._heuristic_classification(structure)

                if structure_type in ("single_album", "multi_disc_album"):
                    metadata = self.directory_analyzer.extract_folder_metadata(folder)
                    if metadata.get("total_files", 0) > 0:
                        job = ProposalJob(folder=folder, metadata=metadata)
                        success = getattr(self.background_processor, "submit_job", lambda _: False)(job)
                        if success:
                            count += 1
                            console.print(
                                f"[dim]Queued background proposal for {folder.name}[/dim]"
                            )
                        else:
                            break

                elif structure_type == "artist_collection":
                    # Prefetch at album level with artist hint
                    for subdir in structure.get("subdirectories", []):
                        if max_jobs is not None and count >= max_jobs:
                            break
                        if subdir.get("music_files", 0) <= 0:
                            continue
                        album_folder = folder / subdir["name"]
                        metadata = self.directory_analyzer.extract_folder_metadata(album_folder)
                        if metadata.get("total_files", 0) > 0:
                            job = ProposalJob(
                                folder=album_folder,
                                metadata=metadata,
                                artist_hint=folder.name,
                            )
                            success = getattr(self.background_processor, "submit_job", lambda _: False)(job)
                            if success:
                                count += 1
                                console.print(
                                    f"[dim]Queued background proposal for {album_folder.name}[/dim]"
                                )
                            else:
                                break
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


class OrganizationSession:
    """Manages the lifecycle of an organization session."""

    def __init__(self, organizer: MusicOrganizer):
        self.organizer = organizer

    def start(self):
        """Start the organization session."""
        self.organizer.background_processor.start()

    def stop(self):
        """Stop the organization session and display summary."""
        self.organizer.background_processor.stop()
        self.organizer.ui.display_completion_summary(
            self.organizer.progress_tracker.get_stats()
        )


class FolderDiscovery:
    """Responsible for discovering and filtering folders to process."""

    def __init__(self, source_dir: Path, state_manager):
        self.source_dir = source_dir
        self.state_manager = state_manager

    def discover(self):
        """Discover folders to process."""
        folders = [d for d in self.source_dir.iterdir() if d.is_dir()]

        if not folders:
            console.print("[yellow]No folders found in source directory.[/yellow]")
            return None

        unorganized_folders, organized_count = (
            self.state_manager.filter_unorganized_folders(folders)
        )

        if organized_count > 0:
            console.print(
                f"[yellow]Found {organized_count} already organized folders, skipping them.[/yellow]"
            )

        if not unorganized_folders:
            console.print("[yellow]No unorganized folders found.[/yellow]")
            return None

        console.print(
            f"\n[bold cyan]Found {len(unorganized_folders)} folders to process[/bold cyan]\n"
        )

        return unorganized_folders


class ProcessingPipeline:
    """Orchestrates the processing of multiple folders with background support."""

    def __init__(self, organizer: MusicOrganizer, folders):
        self.organizer = organizer
        self.folders = folders

    def execute(self):
        """Execute the processing pipeline."""
        # Pre-analyze first few folders and submit background jobs
        self.organizer._prefetch_proposals(self.folders)

        for idx, folder in enumerate(self.folders, 1):
            processor = FolderProcessor(self.organizer, folder, idx, len(self.folders))
            processor.process()

            # Background management
            self._manage_background_processing(idx)

    def _manage_background_processing(self, current_idx: int):
        """Manage background processing for remaining folders."""
        # Check for source directory changes
        if self.organizer.background_processor.check_source_dir_changed(
            self.organizer.source_dir
        ):
            console.print(
                "[yellow]Source directory changed, re-analyzing remaining folders...[/yellow]"
            )
            remaining_folders = self.folders[current_idx:]
            if remaining_folders:
                self.organizer._prefetch_proposals(remaining_folders)

        # Pre-submit next folder's job if available
        if current_idx < len(self.folders):
            self.organizer._submit_next_job(self.folders, current_idx - 1)


class FolderProcessor:
    """Processes a single folder through the complete workflow."""

    def __init__(self, organizer: MusicOrganizer, folder: Path, index: int, total: int):
        self.organizer = organizer
        self.folder = folder
        self.index = index
        self.total = total

    def process(self):
        """Process this folder completely."""
        try:
            self.organizer.ui.display_progress(self.index, self.total, self.folder.name)

            # Analyze and classify
            structure_analysis = self._analyze_structure()
            if not structure_analysis:
                return

            structure_type = self._classify_structure(structure_analysis)

            # Process based on type
            success = self.organizer._process_folder_by_type(
                self.folder, structure_type, structure_analysis
            )

            # Update progress tracking
            self._update_progress(success)

            console.print("\n" + "─" * 80 + "\n")

        except Exception as e:
            console.print(f"[red]Error processing {self.folder.name}: {e}[/red]")
            self.organizer.progress_tracker.increment_errors()

    def _analyze_structure(self):
        """Analyze directory structure."""
        console.print("\n[cyan]Analyzing directory structure...[/cyan]")
        structure_analysis = (
            self.organizer.directory_analyzer.analyze_directory_structure(self.folder)
        )

        if structure_analysis["total_music_files"] == 0:
            console.print(
                "[yellow]No music files found in this folder, skipping...[/yellow]"
            )
            self.organizer.progress_tracker.increment_skipped()
            return None

        self.organizer.ui.display_structure_analysis(structure_analysis)
        return structure_analysis

    def _classify_structure(self, structure_analysis):
        """Classify structure type."""
        structure_type = (
            self.organizer.structure_classifier.classify_directory_structure(
                structure_analysis
            )
        )
        console.print(f"[cyan]Detected structure type: {structure_type}[/cyan]")
        return structure_type

    def _update_progress(self, success):
        """Update progress tracking."""
        self.organizer.progress_tracker.increment_processed()
        if not success:
            self.organizer.progress_tracker.increment_skipped()
