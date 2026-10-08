"""POST /v1/jobs and GET /v1/jobs/{job_id} (Checkpoint 10).

Thin router: parses the request, calls JobService, and maps the result onto
the Checkpoint 8 envelope variants. No business logic lives here.
"""

import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from backend.app.api.ingest import get_ingestion_service
from backend.app.core import error_codes
from backend.app.models.api_errors import ApiError, RecoveryHint, RequestLocation
from backend.app.models.api_responses import (
    FailureResponse,
    ProcessingData,
    ProcessingResponse,
    SuccessResponse,
)
from backend.app.models.jobs import ACTIVE_STATES, CreateJobRequest, Job, JobError
from backend.app.repositories.job_repository import InMemoryJobRepository, JobRepository
from backend.app.services.ingestion_service import IngestionService
from backend.app.services.job_service import JobService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["jobs"])

_STAGE = "jobs"
_POLL_AFTER_SECONDS = 2

from backend.app.core.config import settings
from backend.app.repositories.supabase_job_repository import SupabaseJobRepository
from backend.app.services.supabase_client import SupabaseClient

# TEMPORARY per-checkpoint mapping: code -> (HTTP status, ApiError category).
_ERROR_SPECS = {
    error_codes.REQUEST_VALIDATION_FAILED: (400, "request"),
    error_codes.DOCUMENT_UNAVAILABLE: (404, "request"),
    error_codes.JOB_NOT_FOUND: (404, "request"),
    error_codes.INVALID_JOB_STATE_TRANSITION: (409, "processing"),
    error_codes.PERSISTENCE_UNAVAILABLE: (503, "system"),
    error_codes.PERSISTENCE_ERROR: (500, "system"),
}

# Process-wide repository instance; defaults to in-memory, uses Supabase when configured.
_job_repository: JobRepository | None = None


def get_job_repository() -> JobRepository:
    global _job_repository
    if _job_repository is None:
        if settings.is_supabase_configured:
            client = SupabaseClient(
                url=settings.supabase_url or "",
                key=settings.get_effective_supabase_key() or "",
            )
            _job_repository = SupabaseJobRepository(client)
        else:
            _job_repository = InMemoryJobRepository()
    return _job_repository


def reset_job_repository(repo: JobRepository | None = None) -> None:
    """Reset or override the process-wide job repository instance (useful for testing)."""
    global _job_repository
    _job_repository = repo



def get_job_service(
    repository: JobRepository = Depends(get_job_repository),
    ingestion: IngestionService = Depends(get_ingestion_service),
) -> JobService:
    return JobService(repository, document_exists=ingestion.has_document)


# ------------------------------------------------------------------ helpers
def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def _job_url(job_id: str) -> str:
    return f"/v1/jobs/{job_id}"  # logical API URL, never host- or machine-specific


def _failure(
    request_id: str,
    error: ApiError,
    status_code: int,
    *,
    job_id: str | None = None,
    document_id: str | None = None,
) -> JSONResponse:
    body = FailureResponse(
        request_id=request_id,
        message=error.message,
        job_id=job_id,
        document_id=document_id,
        errors=[error],
    )
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json"))


def _domain_failure(request_id: str, exc: JobError) -> JSONResponse:
    status_code, category = _ERROR_SPECS.get(exc.code, (500, "internal"))
    error = ApiError(
        error_id=_new_id("err"),
        code=exc.code,
        category=category,
        message=exc.message,
        recoverable=False,
        stage=_STAGE,
        location=RequestLocation(field_path=exc.field_path) if exc.field_path else None,
    )
    return _failure(request_id, error, status_code)


def _internal_failure(request_id: str) -> JSONResponse:
    error = ApiError(
        error_id=_new_id("err"),
        code=error_codes.INTERNAL_ERROR,
        category="internal",
        message="The request could not be processed. Please try again.",
        recoverable=True,
        recovery=RecoveryHint(action="retry", owner="client", retry_after_seconds=5),
        stage=_STAGE,
    )
    return _failure(request_id, error, 500)


def _processing(request_id: str, job: Job, message: str, status_code: int, **kw) -> JSONResponse:
    body = ProcessingResponse[Job](
        request_id=request_id,
        message=message,
        job_id=job.job_id,
        document_id=job.document_id,
        data=ProcessingData[Job](
            job_url=_job_url(job.job_id),
            state=job.state,
            stage=job.stage,
            progress=job.progress,
            partial_result=None,
            poll_after_seconds=_POLL_AFTER_SECONDS,
            parent_job_id=job.parent_job_id,
        ),
        errors=[],
        meta={},
    )
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json"), **kw)


def _status_response(request_id: str, job: Job) -> JSONResponse:
    if job.state in ACTIVE_STATES:
        return _processing(request_id, job, "Job is in progress.", 200)

    if job.state == "failed":
        # C10 stores no failure reason; later checkpoints attach a real ApiError.
        error = ApiError(
            error_id=_new_id("err"),
            code=error_codes.INTERNAL_ERROR,
            category="processing",
            message="The job failed.",
            recoverable=False,
            stage=job.stage,
            details={"job_state": "failed"},
        )
        return _failure(request_id, error, 200, job_id=job.job_id, document_id=job.document_id)

    message = "Job completed." if job.state == "completed" else "Job was cancelled."
    body = SuccessResponse[Job](
        request_id=request_id,
        message=message,
        job_id=job.job_id,
        document_id=job.document_id,
        data=job,
        errors=[],
        meta={},
    )
    return JSONResponse(status_code=200, content=body.model_dump(mode="json"))


# ---------------------------------------------------------------- endpoints
@router.post(
    "/jobs",
    status_code=202,
    response_model=None,
    summary="Create a processing job for an ingested document",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"application/json": {"schema": CreateJobRequest.model_json_schema()}},
        }
    },
)
async def create_job(request: Request, service: JobService = Depends(get_job_service)) -> JSONResponse:
    request_id = _new_id("req")

    # Parsed manually so invalid bodies yield the standard envelope, not FastAPI's 422.
    try:
        payload = CreateJobRequest.model_validate_json(await request.body())
    except ValidationError:
        error = ApiError(
            error_id=_new_id("err"),
            code=error_codes.REQUEST_VALIDATION_FAILED,
            category="request",
            message="The request body is invalid. Expected JSON with 'document_id' "
            "and optional 'parent_job_id'.",
            recoverable=False,
            stage=_STAGE,
            location=RequestLocation(field_path=["body"]),
        )
        return _failure(request_id, error, 400)

    try:
        job = await service.create_job(payload.document_id, payload.parent_job_id)
    except JobError as exc:
        return _domain_failure(request_id, exc)
    except Exception:
        logger.exception("Unexpected failure while creating a job")
        return _internal_failure(request_id)

    return _processing(
        request_id, job, "Job created.", 202, headers={"Location": _job_url(job.job_id)}
    )


@router.get("/jobs/{job_id}", response_model=None, summary="Get job status")
async def get_job(job_id: str, service: JobService = Depends(get_job_service)) -> JSONResponse:
    request_id = _new_id("req")
    try:
        job = await service.get_job(job_id)
    except JobError as exc:
        return _domain_failure(request_id, exc)
    except Exception:
        logger.exception("Unexpected failure while reading a job")
        return _internal_failure(request_id)
    return _status_response(request_id, job)
