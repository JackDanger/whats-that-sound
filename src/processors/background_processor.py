"""Background processing for LLM inference to improve UI responsiveness."""

import threading
import queue
from pathlib import Path
from typing import Dict, Optional, Callable
from dataclasses import dataclass
from rich.console import Console

console = Console()


@dataclass
class ProposalJob:
    """Represents a proposal generation job."""

    folder: Path
    metadata: Dict
    user_feedback: Optional[str] = None
    artist_hint: Optional[str] = None
    job_id: str = None

    def __post_init__(self):
        if self.job_id is None:
            self.job_id = str(self.folder)


@dataclass
class ProposalResult:
    """Represents the result of a proposal generation job."""

    job_id: str
    proposal: Dict
    error: Optional[str] = None


class BackgroundProposalProcessor:
    """Processes LLM proposal generation in background threads."""

    def __init__(self, proposal_generator, max_prefetch: int = 2):
        """Initialize the background processor.

        Args:
            proposal_generator: ProposalGenerator instance
            max_prefetch: Maximum number of proposals to prefetch ahead
        """
        self.proposal_generator = proposal_generator
        self.max_prefetch = max_prefetch

        # Thread-safe queues
        self.job_queue = queue.Queue(maxsize=max_prefetch * 2)
        self.result_queue = queue.Queue()

        # Worker thread
        self.worker_thread = None
        self.shutdown_event = threading.Event()

        # Cache for completed proposals
        self.proposal_cache: Dict[str, ProposalResult] = {}

        # Source directory monitoring
        self.source_dir_mtime: Optional[float] = None

    def start(self):
        """Start the background worker thread."""
        if self.worker_thread is not None and self.worker_thread.is_alive():
            return

        self.shutdown_event.clear()
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True, name="proposal-worker")
        self.worker_thread.start()
        console.print("[dim]Background proposal processor started[/dim]")

    def stop(self):
        """Stop the background worker thread."""
        if self.worker_thread is None:
            return

        self.shutdown_event.set()

        # Clear queues to unblock worker
        try:
            while not self.job_queue.empty():
                self.job_queue.get_nowait()
        except queue.Empty:
            pass

        if self.worker_thread.is_alive():
            self.worker_thread.join(timeout=2.0)

        console.print("[dim]Background proposal processor stopped[/dim]")

    def submit_job(self, job: ProposalJob) -> bool:
        """Submit a proposal generation job.

        Args:
            job: ProposalJob to process

        Returns:
            True if job was queued, False if queue is full
        """
        try:
            # Check if we already have this result cached
            if job.job_id in self.proposal_cache:
                return True

            self.job_queue.put_nowait(job)
            return True
        except queue.Full:
            console.print(
                "[yellow]Background job queue is full, will process synchronously[/yellow]"
            )
            return False

    def get_proposal(
        self, job_id: str, timeout: float = 0.1
    ) -> Optional[ProposalResult]:
        """Get a completed proposal result.

        Args:
            job_id: Job ID to retrieve result for
            timeout: Maximum time to wait for result

        Returns:
            ProposalResult if available, None otherwise
        """
        # Check cache first
        if job_id in self.proposal_cache:
            return self.proposal_cache.pop(job_id)

        # Check if result is ready
        try:
            while True:
                result = self.result_queue.get_nowait()
                if result.job_id == job_id:
                    return result
                else:
                    # Cache result for later
                    self.proposal_cache[result.job_id] = result
        except queue.Empty:
            return None

    def wait_for_proposal(
        self, job_id: str, timeout: float = 30.0
    ) -> Optional[ProposalResult]:
        """Wait for a specific proposal result.

        Args:
            job_id: Job ID to wait for
            timeout: Maximum time to wait

        Returns:
            ProposalResult if completed within timeout, None otherwise
        """
        # Check cache first
        if job_id in self.proposal_cache:
            return self.proposal_cache.pop(job_id)

        # Wait for result
        start_time = threading.Event()
        start_time.clear()

        while timeout > 0:
            try:
                result = self.result_queue.get(timeout=min(timeout, 0.5))
                if result.job_id == job_id:
                    return result
                else:
                    # Cache result for later
                    self.proposal_cache[result.job_id] = result
                timeout -= 0.5
            except queue.Empty:
                timeout -= 0.5
                continue

        return None

    def check_source_dir_changed(self, source_dir: Path) -> bool:
        """Check if source directory has been modified.

        Args:
            source_dir: Source directory to check

        Returns:
            True if directory has been modified since last check
        """
        try:
            current_mtime = source_dir.stat().st_mtime
            if self.source_dir_mtime is None:
                self.source_dir_mtime = current_mtime
                return False

            changed = current_mtime != self.source_dir_mtime
            if changed:
                console.print(
                    "[yellow]Source directory has been modified, clearing cache[/yellow]"
                )
                self.clear_cache()
                self.source_dir_mtime = current_mtime

            return changed
        except OSError:
            # Directory might not exist or be accessible
            return True

    def clear_cache(self):
        """Clear the proposal cache."""
        self.proposal_cache.clear()

        # Clear result queue
        try:
            while not self.result_queue.empty():
                self.result_queue.get_nowait()
        except queue.Empty:
            pass

    def _worker_loop(self):
        """Main worker thread loop."""
        console.print("[dim]Background worker thread started[/dim]")

        while not self.shutdown_event.is_set():
            try:
                # Get next job with timeout
                job = self.job_queue.get(timeout=1.0)

                if self.shutdown_event.is_set():
                    break

                console.print(
                    f"[dim]Processing proposal for {job.folder.name} in background[/dim]"
                )

                # Generate proposal
                result = self._process_job(job)

                # Queue result
                try:
                    self.result_queue.put_nowait(result)
                except queue.Full:
                    # If result queue is full, drop oldest results
                    console.print(
                        "[yellow]Result queue full, dropping old results[/yellow]"
                    )
                    try:
                        self.result_queue.get_nowait()  # Drop one
                        self.result_queue.put_nowait(result)  # Add new one
                    except queue.Empty:
                        pass

            except queue.Empty:
                continue
            except Exception as e:
                console.print(f"[red]Error in background worker: {e}[/red]")

        console.print("[dim]Background worker thread stopped[/dim]")

    def _process_job(self, job: ProposalJob) -> ProposalResult:
        """Process a single proposal job.

        Args:
            job: ProposalJob to process

        Returns:
            ProposalResult with proposal or error
        """
        try:
            proposal = self.proposal_generator.get_llm_proposal(
                job.metadata, job.user_feedback, job.artist_hint
            )

            return ProposalResult(job_id=job.job_id, proposal=proposal)

        except Exception as e:
            return ProposalResult(job_id=job.job_id, proposal=None, error=str(e))
