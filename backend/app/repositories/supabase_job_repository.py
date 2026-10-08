"""Supabase-backed Job Repository (Checkpoint 14).

Implements the async JobRepository interface backed by Supabase PostgREST tables.
"""

from typing import Any, Callable
import logging

from backend.app.core import error_codes
from backend.app.models.jobs import (
    ACTIVE_STATES,
    Job,
    JobError,
    JobNotFoundError,
)
from backend.app.repositories.job_repository import DuplicateJobError, JobRepository
from backend.app.services.supabase_client import (
    SupabaseApiError,
    SupabaseClient,
    SupabaseConnectionError,
)

logger = logging.getLogger(__name__)


class PersistenceUnavailableError(JobError):
    code = error_codes.PERSISTENCE_UNAVAILABLE


class SupabaseJobRepository(JobRepository):
    """PostgREST/Supabase persistence for Jobs.

    Replaces InMemoryJobRepository in production environments while keeping
    JobService completely unchanged.
    """

    def __init__(self, client: SupabaseClient, table: str = "jobs") -> None:
        self.client = client
        self.table = table

    # ------------------------------------------------------------- serialize
    @staticmethod
    def _to_record(job: Job) -> dict[str, Any]:
        """Convert a Job instance to a database-friendly dictionary."""
        data = job.model_dump(mode="json")
        # Ensure timestamps are ISO strings
        data["created_at"] = job.created_at.isoformat()
        data["updated_at"] = job.updated_at.isoformat()
        if job.progress is not None:
            data["progress"] = job.progress.model_dump(mode="json")
        return data

    @staticmethod
    def _from_record(record: dict[str, Any]) -> Job:
        """Construct a validated Job instance from a database record."""
        return Job.model_validate(record)

    # ------------------------------------------------------------- interface
    async def create(self, job: Job) -> Job:
        record = self._to_record(job)
        try:
            # Check for existing record to enforce DuplicateJobError contract
            existing = await self.get(job.job_id)
            if existing is not None:
                raise DuplicateJobError("job already exists")

            await self.client.insert(self.table, record)
            return job.model_copy(deep=True)
        except SupabaseConnectionError as exc:
            raise PersistenceUnavailableError("Persistence service is unavailable.") from exc
        except SupabaseApiError as exc:
            if exc.status_code == 409 or "duplicate key" in str(exc.details).lower():
                raise DuplicateJobError("job already exists") from exc
            raise PersistenceUnavailableError(f"Database error creating job: {exc.message}") from exc

    async def get(self, job_id: str) -> Job | None:
        try:
            records = await self.client.select(self.table, {"job_id": f"eq.{job_id}"})
            if not records:
                return None
            return self._from_record(records[0])
        except SupabaseConnectionError as exc:
            raise PersistenceUnavailableError("Persistence service is unavailable.") from exc
        except SupabaseApiError as exc:
            if exc.status_code == 404:
                return None
            raise PersistenceUnavailableError(f"Database error reading job: {exc.message}") from exc

    async def update(self, job: Job) -> Job:
        record = self._to_record(job)
        try:
            records = await self.client.update(
                self.table,
                record,
                match_params={"job_id": f"eq.{job.job_id}"},
            )
            if not records:
                # PostgREST returns empty list when no row matched
                raise JobNotFoundError("The job was not found.")
            return job.model_copy(deep=True)
        except SupabaseConnectionError as exc:
            raise PersistenceUnavailableError("Persistence service is unavailable.") from exc
        except SupabaseApiError as exc:
            if exc.status_code == 404:
                raise JobNotFoundError("The job was not found.") from exc
            raise PersistenceUnavailableError(f"Database error updating job: {exc.message}") from exc

    async def modify(self, job_id: str, mutator: Callable[[Job], Job]) -> Job:
        current = await self.get(job_id)
        if current is None:
            raise JobNotFoundError("The job was not found.")

        updated = mutator(current.model_copy(deep=True))
        if updated.job_id != job_id:
            raise ValueError("mutator must not change job_id")

        return await self.update(updated)

    async def delete(self, job_id: str) -> bool:
        try:
            records = await self.client.delete(self.table, {"job_id": f"eq.{job_id}"})
            return bool(records)
        except SupabaseConnectionError as exc:
            raise PersistenceUnavailableError("Persistence service is unavailable.") from exc
        except SupabaseApiError as exc:
            if exc.status_code == 404:
                return False
            raise PersistenceUnavailableError(f"Database error deleting job: {exc.message}") from exc

    async def clear(self) -> None:
        try:
            # Delete all rows where job_id is not empty
            await self.client.delete(self.table, {"job_id": "neq."})
        except SupabaseConnectionError as exc:
            raise PersistenceUnavailableError("Persistence service is unavailable.") from exc
        except SupabaseApiError:
            pass

    # ------------------------------------------------------------- recovery
    async def list_active_jobs(self) -> list[Job]:
        """Fetch all jobs currently in an active (non-terminal) state."""
        try:
            states_csv = ",".join(sorted(ACTIVE_STATES))
            records = await self.client.select(self.table, {"state": f"in.({states_csv})"})
            return [self._from_record(r) for r in records]
        except SupabaseConnectionError as exc:
            raise PersistenceUnavailableError("Persistence service is unavailable.") from exc
        except SupabaseApiError as exc:
            raise PersistenceUnavailableError(f"Database error querying active jobs: {exc.message}") from exc
