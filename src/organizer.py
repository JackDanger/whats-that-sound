"""Main music organization orchestrator."""

from pathlib import Path
 

from .analyzers import DirectoryAnalyzer, StructureClassifier
from .inference import InferenceProvider
from .organizers import FileOrganizer
from .trackers import ProgressTracker, StateManager
from .jobs import SQLiteJobStore
import multiprocessing
import os
from .worker import run_scan_worker, run_analyze_worker, run_move_worker
import logging
logger = logging.getLogger("wts.organizer")
from pathlib import Path


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
        self.jobstore = SQLiteJobStore()

        # Dedicated single-purpose worker processes
        self.worker_processes: list[multiprocessing.Process] = []
        for target in (run_scan_worker, run_analyze_worker, run_move_worker):
            p = multiprocessing.Process(target=target, daemon=True)
            logger.info(f"Starting worker process {target}")
            p.start()
            self.worker_processes.append(p)

        # No in-process processors needed for web UI + workers

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


 


 
