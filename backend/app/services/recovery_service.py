"""Failure and restart recovery service for background jobs (Checkpoint 14).

Identifies interrupted, stalled, or unfinalized jobs following a backend crash,
restart, or timeout, and transitions them safely according to the job state machine.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal
import logging

from backend.app.core import error_codes
from backend.app.models.jobs import (
    ACTIVE_STATES,
    ALLOWED_TRANSITIONS,
    TERMINAL_STATES,
    Job,
)
from backend.app.repositories.job_repository import JobRepository
from backend.app.services.job_service import JobService
from backend.app.services.persistence_service import PersistenceService

logger = logging.getLogger(__name__)


@dataclass
class JobRecoveryReport:
    job_id: str
    original_state: str
    new_state: str
    recovered: bool
    reason: str


@dataclass
class RecoverySummary:
    total_active_scanned: int = 0
    recovered_count: int = 0
    reports: list[JobRecoveryReport] = field(default_factory=list)


class JobRecoveryService:
    """Detects and reconciles orphaned jobs across system lifecycles."""

    def __init__(
        self,
        repository: JobRepository,
        job_service: JobService,
        persistence_service: PersistenceService | None = None,
        stale_timeout_seconds: int = 3600,
    ) -> None:
        self.repository = repository
        self.job_service = job_service
        self.persistence = persistence_service
        self.stale_timeout_seconds = stale_timeout_seconds

    async def recover_interrupted_jobs(
        self,
        *,
        action: Literal["fail", "retry"] = "fail",
        force_active: bool = False,
    ) -> RecoverySummary:
        """Scan active jobs and transition orphaned jobs safely.

        - If `force_active=True`, all jobs currently in an active state are treated
          as interrupted by a restart.
        - If `force_active=False`, only jobs whose `updated_at` timestamp exceeds
          `stale_timeout_seconds` are treated as interrupted.
        """
        summary = RecoverySummary()
        now = datetime.now(timezone.utc)

        # Retrieve active jobs from repository
        active_jobs: list[Job] = []
        if hasattr(self.repository, "list_active_jobs"):
            active_jobs = await self.repository.list_active_jobs()
        else:
            # Fallback for repositories without list_active_jobs: inspect internal store if available
            jobs_dict = getattr(self.repository, "_jobs", {})
            active_jobs = [j for j in jobs_dict.values() if j.state in ACTIVE_STATES]

        summary.total_active_scanned = len(active_jobs)

        for job in active_jobs:
            if job.state in TERMINAL_STATES:
                continue

            age_seconds = (now - job.created_at).total_seconds()
            is_stale = force_active or (age_seconds >= self.stale_timeout_seconds)

            if not is_stale:
                continue

            report = await self._reconcile_job(job, action=action, age_seconds=age_seconds)
            summary.reports.append(report)
            if report.recovered:
                summary.recovered_count += 1

        return summary

    async def _reconcile_job(
        self,
        job: Job,
        action: Literal["fail", "retry"],
        age_seconds: float,
    ) -> JobRecoveryReport:
        orig_state = job.state
        target_state: str = "failed"
        reason = f"Interrupted after {int(age_seconds)}s without completion."

        if action == "retry":
            if "retry_wait" in ALLOWED_TRANSITIONS.get(orig_state, ()):
                target_state = "retry_wait"
            elif "queued" in ALLOWED_TRANSITIONS.get(orig_state, ()):
                target_state = "queued"
            else:
                target_state = "failed"

        # Check if transition is valid
        if target_state not in ALLOWED_TRANSITIONS.get(orig_state, ()):
            return JobRecoveryReport(
                job_id=job.job_id,
                original_state=orig_state,
                new_state=orig_state,
                recovered=False,
                reason=f"Transition from {orig_state} to {target_state} not permitted.",
            )

        try:
            await self.job_service.transition_job(job.job_id, target_state)

            # Record outcome metadata if persistence service is configured
            if self.persistence:
                await self.persistence.record_processing_outcome(
                    job_id=job.job_id,
                    document_id=job.document_id,
                    status=target_state,
                    error_code=error_codes.TIMEOUT if target_state == "failed" else None,
                    error_message=reason,
                    partial_results={
                        "interrupted_state": orig_state,
                        "recovered_to": target_state,
                        "recovery_timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                )

            return JobRecoveryReport(
                job_id=job.job_id,
                original_state=orig_state,
                new_state=target_state,
                recovered=True,
                reason=reason,
            )
        except Exception as exc:
            logger.error("Failed to recover job %s: %s", job.job_id, exc)
            return JobRecoveryReport(
                job_id=job.job_id,
                original_state=orig_state,
                new_state=orig_state,
                recovered=False,
                reason=f"Error during transition: {exc}",
            )
