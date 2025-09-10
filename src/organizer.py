"""Main music organization orchestrator."""

from pathlib import Path
 

from .analyzers import DirectoryAnalyzer, StructureClassifier
from .inference import InferenceProvider
from .organizers import FileOrganizer
from .processors import AlbumProcessor, CollectionProcessor
from .trackers import ProgressTracker, StateManager
from .jobs import SQLiteJobStore
import multiprocessing
import os
from .worker import run_scan_worker, run_analyze_worker, run_move_worker
import threading
import time
import logging
logger = logging.getLogger("wts.organizer")
from pathlib import Path
from dataclasses import dataclass

 


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
        logger.info(f"Configuring inference provider (model: {model_path.name})")
        self.inference = InferenceProvider()

        # Initialize components
        self._initialize_components()

    def _initialize_components(self):
        """Initialize all the specialized components."""
        # Core components
        self.directory_analyzer = DirectoryAnalyzer()
        self.structure_classifier = StructureClassifier(self.inference)
        self.file_organizer = FileOrganizer(self.target_dir)
        self.progress_tracker = ProgressTracker()
        self.state_manager = StateManager()
        # Terminal UI removed; web UI is primary
        self.jobstore = SQLiteJobStore()

        # Dedicated single-purpose worker processes
        self.worker_processes: list[multiprocessing.Process] = []
        for target in (run_scan_worker, run_analyze_worker, run_move_worker):
            p = multiprocessing.Process(target=target, daemon=True)
            logger.info(f"Starting worker process {target}")
            p.start()
            self.worker_processes.append(p)

        # Processors
        self.album_processor = AlbumProcessor(
            self.directory_analyzer,
            self.file_organizer,
            self.state_manager,
        )

        self.collection_processor = CollectionProcessor(
            self.directory_analyzer,
            self.file_organizer,
            self.state_manager,
        )

    def update_paths(self, source_dir: Path, target_dir: Path) -> None:
        """Update source/target directories and refresh dependent components without spawning a new worker.

        This keeps the existing worker process and job store, but refreshes path-dependent
        components and progress tracking for a new session.
        """
        self.source_dir = source_dir
        self.target_dir = target_dir
        # Refresh components that depend on target/source paths
        self.file_organizer = FileOrganizer(self.target_dir)
        # Reset progress tracking for a new run
        self.progress_tracker = ProgressTracker()

    def organize(self):
        """Main organization workflow with background processing."""
        session = OrganizationSession(self)
        try:
            session.start()
            # Live dashboard handled by web UI

            folders = FolderDiscovery(self.source_dir, self.state_manager).discover()
            if not folders:
                return

            # Reset any stale analyzing jobs (e.g., after crash/CTRL-C)
            try:
                reset = self.jobstore.reset_stale_analyzing()
                if reset:
                    logger.info(f"Re-queued {reset} stale jobs from previous run")
            except Exception:
                pass

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
            logger.error(f"Unknown structure type: {structure_type}")
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
                        # Always enqueue via job store; dedicated worker will process
                        if self.jobstore.has_any_for_folder(folder):
                            continue
                        self.jobstore.enqueue(folder, metadata)
                        success = True
                        if success:
                            count += 1
                            logger.info(
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
                            if self.jobstore.has_any_for_folder(album_folder):
                                continue
                            self.jobstore.enqueue(album_folder, metadata, artist_hint=folder.name)
                            success = True
                            if success:
                                count += 1
                                logger.info(
                                    f"[dim]Queued background proposal for {album_folder.name}[/dim]"
                                )
                            else:
                                break
            except Exception as e:
                logger.error(
                    f"[yellow]Could not queue background job for {folder.name}: {e}[/yellow]"
                )

    def _submit_next_job(self, folders, current_idx: int):
        """Submit analyze job for the next folder to keep pipeline warm."""
        next_idx = current_idx + 2
        if next_idx < len(folders):
            folder = folders[next_idx]
            try:
                metadata = self.directory_analyzer.extract_folder_metadata(folder)
                if metadata.get("total_files", 0) > 0 and not self.jobstore.has_any_for_folder(folder):
                    self.jobstore.enqueue(folder, metadata)
            except Exception:
                pass


class OrganizationSession:
    """Manages the lifecycle of an organization session."""

    def __init__(self, organizer: MusicOrganizer):
        self.organizer = organizer

    def start(self):
        """Start the organization session."""
        # Background processor removed; worker started at init

    def stop(self):
        """Stop the organization session and display summary."""
        # Let worker run; nothing to stop here for now
        # No terminal summary; web UI shows status


class FolderDiscovery:
    """Responsible for discovering and filtering folders to process."""

    def __init__(self, source_dir: Path, state_manager):
        self.source_dir = source_dir
        self.state_manager = state_manager

    def discover(self):
        """Discover folders to process."""
        folders = [d for d in self.source_dir.iterdir() if d.is_dir()]

        if not folders:
            logger.warning("No folders found in source directory.")
            return None

        unorganized_folders, organized_count = (
            self.state_manager.filter_unorganized_folders(folders)
        )

        if organized_count > 0:
            logger.warning(
                f"[yellow]Found {organized_count} already organized folders, skipping them.[/yellow]"
            )

        if not unorganized_folders:
            logger.warning("No unorganized folders found.")
            return None

        logger.info(
            f"\n[bold cyan]Found {len(unorganized_folders)} folders to process[/bold cyan]\n"
        )

        return unorganized_folders


class ProcessingPipeline:
    """Orchestrates the processing of multiple folders with background support."""

    def __init__(self, organizer: MusicOrganizer, folders):
        self.organizer = organizer
        self.folders = folders

    def execute(self):
        """Execute the processing pipeline using the presenter for clarity."""
        presenter = DecisionPresenter(self.organizer, self.folders)
        presenter.run()


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

        except Exception as e:
            logger.error(f"Error processing {self.folder.name}: {e}")
            self.organizer.progress_tracker.increment_errors()

    def _analyze_structure(self):
        """Analyze directory structure."""
        logger.info("Analyzing directory structure...")
        structure_analysis = (
            self.organizer.directory_analyzer.analyze_directory_structure(self.folder)
        )

        if structure_analysis["total_music_files"] == 0:
            logger.warning(
                "[yellow]No music files found in this folder, skipping...[/yellow]"
            )
            self.organizer.progress_tracker.increment_skipped()
            return None

        # Web UI displays structure
        return structure_analysis

    def _classify_structure(self, structure_analysis):
        """Classify structure type."""
        structure_type = (
            self.organizer.structure_classifier.classify_directory_structure(
                structure_analysis
            )
        )
        logger.info(f"Detected structure type: {structure_type}")
        return structure_type

    def _update_progress(self, success):
        """Update progress tracking."""
        self.organizer.progress_tracker.increment_processed()
        if not success:
            self.organizer.progress_tracker.increment_skipped()


class ProgressRefresher:
    """Displays periodic jobstore progress without flooding the UI."""

    def __init__(self, organizer: MusicOrganizer, interval: float = 1.0):
        self.organizer = organizer
        self.interval = interval
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._recent: list[str] = []

    def start(self):
        self._stop.clear()
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=1.0)

    def _run(self):
        while not self._stop.is_set():
            try:
                counts = self.organizer.jobstore.counts()
                queued = counts.get("queued", 0)
                analyzing = counts.get("analyzing", 0)
                approved = counts.get("ready", 0)
                moving = counts.get("moving", 0)
                skipped = counts.get("skipped", 0)
                errors = counts.get("error", 0)
                completed = counts.get("completed", 0)
                # Fetch a few recently approved items to show
                approved_list = self.organizer.jobstore.fetch_ready(limit=3)
                lines = [f"Queue: {queued} | Analyzing: {analyzing} | Ready: {approved} | Moving: {moving} | Skipped: {skipped} | Errors: {errors} | Completed: {completed}"]
                for _, folder_path, _ in approved_list:
                    lines.append(f"Ready: {Path(folder_path).name}")
                panel_text = "\n".join(lines)
                logger.info(panel_text)
            except Exception:
                pass
            time.sleep(self.interval)


@dataclass
class PresenterState:
    total: int
    processed: int
    pending: list


class DecisionPresenter:
    """Encapsulates the decision-first loop and dashboard rendering."""

    def __init__(self, organizer: MusicOrganizer, folders: list[Path]):
        self.organizer = organizer
        self.state = PresenterState(total=len(folders), processed=0, pending=list(folders))

    def _present_decision(self, folder: Path, proposal: dict) -> bool:
        # Show context
        metadata = self.organizer.directory_analyzer.extract_folder_metadata(folder)

        if feedback["action"] == "accept":
            self.organizer.state_manager.save_proposal_tracker(folder, proposal)
            self.organizer.file_organizer.organize_folder(folder, proposal)
            self.organizer.progress_tracker.increment_processed()
            self.organizer.progress_tracker.increment_successful(proposal)
            return True
        elif feedback["action"] == "reconsider":
            # Enqueue reconsideration
            self.organizer.jobstore.enqueue(folder, metadata, user_feedback=feedback.get("feedback"))
            return False
        elif feedback["action"] == "skip":
            self.organizer.progress_tracker.increment_processed()
            self.organizer.progress_tracker.increment_skipped()
            return True
        elif feedback["action"] == "cancel":
            raise KeyboardInterrupt()
        return False

    def run(self):
        # Pre-enqueue everything we can up front
        self.organizer._prefetch_proposals(self.state.pending)

        refresher = ProgressRefresher(self.organizer)
        refresher.start()
        try:
            while self.state.pending:

                # Drain ready decisions first
                made_progress = False
                for folder in list(self.state.pending):
                    ready = self.organizer.jobstore.get_result(folder)
                    if not ready:
                        continue
                    logger.info(
                        self.state.total - len(self.state.pending) + 1, self.state.total, folder.name
                    )
                    acted = self._present_decision(folder, ready)
                    if acted:
                        self.state.pending.remove(folder)
                    made_progress = True
                if made_progress:
                    continue

                # If nothing ready, process the next folder to keep pipeline moving
                folder = self.state.pending.pop(0)
                processor = FolderProcessor(
                    self.organizer,
                    folder,
                    self.state.total - len(self.state.pending),
                    self.state.total,
                )
                processor.process()
        finally:
            refresher.stop()
