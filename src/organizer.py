"""Main music organization orchestrator."""

from pathlib import Path
 

from .inference import InferenceProvider
from .analyzers import DirectoryAnalyzer, StructureClassifier
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

    def __init__(self, inference: InferenceProvider, model_path: Path, source_dir: Path, target_dir: Path):
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
        self.inference = inference

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

        # Dedicated single-purpose worker processes (disabled under test)
        self.worker_processes: list[multiprocessing.Process] = []
        is_test_env = bool(os.getenv("PYTEST_CURRENT_TEST")) or os.getenv("WTS_DISABLE_WORKERS") == "1"
        if not is_test_env:
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


 


 
