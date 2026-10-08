"""Job repository interface and in-memory implementation (Checkpoint 10).

The interface is async so a later Supabase-backed implementation can replace
the in-memory one without changing JobService.
"""

import threading
from abc import ABC, abstractmethod
from typing import Callable

from backend.app.models.jobs import Job, JobNotFoundError


class DuplicateJobError(Exception):
    """Raised when creating a job whose job_id already exists."""


class JobRepository(ABC):
    @abstractmethod
    async def create(self, job: Job) -> Job: ...

    @abstractmethod
    async def get(self, job_id: str) -> Job | None: ...

    @abstractmethod
    async def update(self, job: Job) -> Job:
        """Replace an existing job. Raises JobNotFoundError if absent."""

    @abstractmethod
    async def modify(self, job_id: str, mutator: Callable[[Job], Job]) -> Job:
        """Atomic read-modify-write. If `mutator` raises, nothing is stored."""

    @abstractmethod
    async def delete(self, job_id: str) -> bool: ...

    @abstractmethod
    async def clear(self) -> None: ...


class InMemoryJobRepository(JobRepository):
    """Process-local storage.

    A threading.Lock guards the critical sections. They contain no awaits, so
    it never blocks the event loop for long, and unlike asyncio.Lock it is not
    bound to one event loop (TestClient creates a new loop per request).
    Callers only ever receive deep copies; the internal dict is never exposed.
    """

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    async def create(self, job: Job) -> Job:
        with self._lock:
            if job.job_id in self._jobs:
                raise DuplicateJobError("job already exists")
            self._jobs[job.job_id] = job.model_copy(deep=True)
            return job.model_copy(deep=True)

    async def get(self, job_id: str) -> Job | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return job.model_copy(deep=True) if job is not None else None

    async def update(self, job: Job) -> Job:
        with self._lock:
            if job.job_id not in self._jobs:
                raise JobNotFoundError("The job was not found.")
            self._jobs[job.job_id] = job.model_copy(deep=True)
            return job.model_copy(deep=True)

    async def modify(self, job_id: str, mutator: Callable[[Job], Job]) -> Job:
        with self._lock:
            current = self._jobs.get(job_id)
            if current is None:
                raise JobNotFoundError("The job was not found.")
            updated = mutator(current.model_copy(deep=True))
            if updated.job_id != job_id:
                raise ValueError("mutator must not change job_id")
            self._jobs[job_id] = updated.model_copy(deep=True)
            return updated.model_copy(deep=True)

    async def delete(self, job_id: str) -> bool:
        with self._lock:
            return self._jobs.pop(job_id, None) is not None

    async def clear(self) -> None:
        with self._lock:
            self._jobs.clear()
