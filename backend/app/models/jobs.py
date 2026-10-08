"""Job models, state machine table and domain errors (Checkpoint 10).

Contract/domain definitions only: no storage, no HTTP, no processing.
"""

from datetime import datetime, timezone
from types import MappingProxyType
from typing import Annotated, Literal, Mapping

from pydantic import AfterValidator, AwareDatetime, ConfigDict, model_validator

from backend.app.core import error_codes
from backend.app.models.api_base import ApiModel, NonEmptyStr
from backend.app.models.api_responses import Progress

JobState = Literal[
    "queued", "running", "retry_wait", "escalating", "completed", "failed", "cancelled"
]

# The active states intentionally mirror ProcessingData.state from Checkpoint 8.
ACTIVE_STATES: frozenset[str] = frozenset({"queued", "running", "retry_wait", "escalating"})
TERMINAL_STATES: frozenset[str] = frozenset({"completed", "failed", "cancelled"})

ALLOWED_TRANSITIONS: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        "queued": frozenset({"running", "cancelled", "failed"}),
        "running": frozenset({"retry_wait", "escalating", "completed", "failed", "cancelled"}),
        "retry_wait": frozenset({"running", "failed", "cancelled"}),
        "escalating": frozenset({"running", "completed", "failed", "cancelled"}),
        "completed": frozenset(),
        "failed": frozenset(),
        "cancelled": frozenset(),
    }
)


def _to_utc(value: datetime) -> datetime:
    return value.astimezone(timezone.utc)


# Timezone-aware only (naive values are rejected); normalized to UTC.
UtcDatetime = Annotated[AwareDatetime, AfterValidator(_to_utc)]


class Job(ApiModel):
    """Job state record. Holds no processing output; later checkpoints attach that."""

    model_config = ConfigDict(frozen=True)  # merged with ApiModel's extra="forbid"

    job_id: NonEmptyStr
    document_id: NonEmptyStr
    state: JobState
    stage: NonEmptyStr | None = None
    progress: Progress | None = None
    parent_job_id: NonEmptyStr | None = None
    created_at: UtcDatetime
    updated_at: UtcDatetime

    @model_validator(mode="after")
    def _consistent(self) -> "Job":
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must not be earlier than created_at")
        if self.parent_job_id is not None and self.parent_job_id == self.job_id:
            raise ValueError("a job cannot be its own parent")
        return self


class CreateJobRequest(ApiModel):
    """Client request. job_id is server-generated, so extra fields (including
    job_id) are rejected by the base model."""

    document_id: NonEmptyStr
    parent_job_id: NonEmptyStr | None = None


# ------------------------------------------------------------------- errors
class JobError(Exception):
    """Base for controlled job-layer errors. Messages are safe for clients."""

    code: str = error_codes.INTERNAL_ERROR

    def __init__(self, message: str, field_path: list[str] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.field_path = field_path


class JobNotFoundError(JobError):
    code = error_codes.JOB_NOT_FOUND


class DocumentNotFoundError(JobError):
    code = error_codes.DOCUMENT_UNAVAILABLE


class InvalidJobRequestError(JobError):
    code = error_codes.REQUEST_VALIDATION_FAILED


class InvalidJobStateTransitionError(JobError):
    code = error_codes.INVALID_JOB_STATE_TRANSITION
