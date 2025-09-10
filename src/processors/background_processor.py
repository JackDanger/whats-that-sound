"""Thin shim around SQLiteJobStore for background analysis (legacy-compatible API).

This module used to manage its own background threads. The system now uses
dedicated worker processes and a SQLite-backed job store. We keep a minimal
interface here to avoid touching older call sites while delegating all work
to the job store.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from ..jobs import SQLiteJobStore


@dataclass
class ProposalJob:
    folder: Path
    metadata: Dict
    user_feedback: Optional[str] = None
    artist_hint: Optional[str] = None
    job_id: Optional[str] = None

    def __post_init__(self):
        if self.job_id is None:
            self.job_id = str(self.folder)


@dataclass
class ProposalResult:
    job_id: str
    proposal: Optional[Dict]
    error: Optional[str] = None


class BackgroundProposalProcessor:
    """Compatibility layer that delegates to SQLiteJobStore-based workers."""

    def __init__(self, proposal_generator=None, max_prefetch: int = 0):
        self.jobstore = SQLiteJobStore()

    # No-ops kept for API compatibility
    def start(self) -> None:
        return None

    def stop(self) -> None:
        return None

    def submit_job(self, job: ProposalJob) -> bool:
        """Enqueue an analyze job if not already present."""
        if not self.jobstore.has_any_for_folder(job.folder):
            self.jobstore.enqueue(
                job.folder,
                job.metadata,
                user_feedback=job.user_feedback,
                artist_hint=job.artist_hint,
                job_type="analyze",
            )
        return True

    def get_proposal(self, job_id: str, timeout: float = 0.0) -> Optional[ProposalResult]:
        folder = Path(job_id)
        res = self.jobstore.get_result(folder)
        if res:
            return ProposalResult(job_id=job_id, proposal=res)
        return None

    def wait_for_proposal(self, job_id: str, timeout: float = 30.0) -> Optional[ProposalResult]:
        folder = Path(job_id)
        res = self.jobstore.wait_for_result(folder, timeout=timeout)
        if res:
            return ProposalResult(job_id=job_id, proposal=res)
        return None
