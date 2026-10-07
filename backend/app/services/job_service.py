"""Job service (Checkpoint 10).

Creates jobs, tracks state, enforces the state machine. It does NOT execute
any processing, retries, or workers.
"""

from datetime import datetime, timezone
from typing import Callable
from uuid import uuid4

from backend.app.models.api_responses import Progress
from backend.app.models.jobs import (
    ACTIVE_STATES,
    ALLOWED_TRANSITIONS,
    TERMINAL_STATES,
    DocumentNotFoundError,
    InvalidJobRequestError,
    InvalidJobStateTransitionError,
    Job,
    JobNotFoundError,
)
from backend.app.repositories.job_repository import JobRepository

Clock = Callable[[], datetime]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _new_job_id() -> str:
    return str(uuid4())


class JobService:
    def __init__(
        self,
        repository: JobRepository,
        document_exists: Callable[[str], bool],
        *,
        clock: Clock = utc_now,
        id_factory: Callable[[], str] = _new_job_id,
    ) -> None:
        self._repository = repository
        self._document_exists = document_exists  # supplied by the C9 ingestion layer
        self._clock = clock
        self._id_factory = id_factory

    # ------------------------------------------------------------- creation
    async def create_job(self, document_id: str, parent_job_id: str | None = None) -> Job:
        document_id = (document_id or "").strip()
        if not document_id:
            raise InvalidJobRequestError("document_id must not be empty.", ["body", "document_id"])
        if parent_job_id is not None:
            parent_job_id = parent_job_id.strip()
            if not parent_job_id:
                raise InvalidJobRequestError(
                    "parent_job_id must not be empty.", ["body", "parent_job_id"]
                )

        if not self._document_exists(document_id):
            raise DocumentNotFoundError(
                "The referenced document is not available.", ["body", "document_id"]
            )
        if parent_job_id is not None and await self._repository.get(parent_job_id) is None:
            raise InvalidJobRequestError(
                "The parent job does not exist.", ["body", "parent_job_id"]
            )

        now = self._clock()
        job = Job(
            job_id=self._id_factory(),
            document_id=document_id,
            state="queued",
            stage="queued",
            progress=None,
            parent_job_id=parent_job_id,
            created_at=now,
            updated_at=now,
        )
        return await self._repository.create(job)

    # ------------------------------------------------------------ retrieval
    async def get_job(self, job_id: str) -> Job:
        job = await self._repository.get(job_id)
        if job is None:
            raise JobNotFoundError("The job was not found.", ["path", "job_id"])
        return job

    # -------------------------------------------------------------- updates
    async def transition_job(self, job_id: str, new_state: str) -> Job:
        def mutate(job: Job) -> Job:
            if new_state not in ALLOWED_TRANSITIONS:
                raise InvalidJobStateTransitionError("Unknown job state.")
            if job.state in TERMINAL_STATES:
                raise InvalidJobStateTransitionError(
                    f"The job is already '{job.state}' and cannot change state."
                )
            if new_state not in ALLOWED_TRANSITIONS[job.state]:
                raise InvalidJobStateTransitionError(
                    f"A job cannot move from '{job.state}' to '{new_state}'."
                )
            return self._changed(job, state=new_state)

        return await self._modify(job_id, mutate)

    async def update_progress(self, job_id: str, progress: Progress | None) -> Job:
        """Store counted progress. Validation lives in the C8 Progress model."""

        def mutate(job: Job) -> Job:
            self._require_active(job)
            return self._changed(job, progress=progress)

        return await self._modify(job_id, mutate)

    async def update_stage(self, job_id: str, stage: str | None) -> Job:
        def mutate(job: Job) -> Job:
            self._require_active(job)
            return self._changed(job, stage=stage)

        return await self._modify(job_id, mutate)

    # -------------------------------------------------------------- helpers
    async def _modify(self, job_id: str, mutate: Callable[[Job], Job]) -> Job:
        try:
            return await self._repository.modify(job_id, mutate)
        except JobNotFoundError as exc:
            raise JobNotFoundError(exc.message, ["path", "job_id"]) from None

    @staticmethod
    def _require_active(job: Job) -> None:
        if job.state not in ACTIVE_STATES:
            raise InvalidJobStateTransitionError(
                f"The job is already '{job.state}' and can no longer be updated."
            )

    def _changed(self, job: Job, **changes) -> Job:
        """Rebuild through validation; updated_at never moves backwards."""
        updated_at = max(self._clock(), job.updated_at)
        return Job.model_validate({**job.model_dump(), **changes, "updated_at": updated_at})
