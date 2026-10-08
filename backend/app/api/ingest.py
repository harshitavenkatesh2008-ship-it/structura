"""POST /v1/ingest (Checkpoint 9).

Thin router: translates the upload into a service call and the result into the
Checkpoint 8 envelope. All validation and storage logic lives in the service.
"""

import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import JSONResponse

from backend.app.core import error_codes
from backend.app.models.api_errors import ApiError, RecoveryHint, RequestLocation
from backend.app.models.api_responses import FailureResponse, SuccessResponse
from backend.app.models.ingestion import IngestedDocument
from backend.app.services.ingestion_service import (
    IngestionError,
    IngestionService,
    IngestionStorageError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["ingestion"])

_STAGE = "ingestion"
_UPLOAD_FIELD_PATH = ["body", "file"]

# TEMPORARY status mapping for this checkpoint only; to be centralized later.
_HTTP_STATUS = {
    error_codes.INVALID_FILE: 400,
    error_codes.UNSUPPORTED_FORMAT: 400,
    error_codes.REQUEST_VALIDATION_FAILED: 400,
    error_codes.DOCUMENT_TOO_LARGE: 413,
    error_codes.INTERNAL_ERROR: 500,
}


def get_ingestion_service() -> IngestionService:
    """Dependency hook; tests override it to point at a temporary directory."""
    return IngestionService()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def _upload_error(code: str, message: str, details: dict | None = None) -> ApiError:
    return ApiError(
        error_id=_new_id("err"),
        code=code,
        category="request",
        message=message,
        recoverable=False,
        recovery=None,
        stage=_STAGE,
        location=RequestLocation(field_path=list(_UPLOAD_FIELD_PATH)),
        details=details or {},
    )


def _internal_error() -> ApiError:
    return ApiError(
        error_id=_new_id("err"),
        code=error_codes.INTERNAL_ERROR,
        category="internal",
        message="The upload could not be processed. Please try again.",
        recoverable=True,
        recovery=RecoveryHint(action="retry", owner="client", retry_after_seconds=5),
        stage=_STAGE,
    )


def _failure(request_id: str, error: ApiError) -> JSONResponse:
    body = FailureResponse(request_id=request_id, message=error.message, errors=[error])
    return JSONResponse(
        status_code=_HTTP_STATUS[error.code], content=body.model_dump(mode="json")
    )


@router.post("/ingest", status_code=201, response_model=None, summary="Upload a document")
async def ingest_document(
    file: UploadFile | None = File(default=None),
    service: IngestionService = Depends(get_ingestion_service),
) -> JSONResponse:
    request_id = _new_id("req")

    if file is None or not (file.filename or "").strip():
        return _failure(
            request_id,
            _upload_error(
                error_codes.REQUEST_VALIDATION_FAILED,
                "A file must be uploaded in the 'file' form field.",
            ),
        )

    try:
        ingested: IngestedDocument = await service.ingest(
            filename=file.filename, content_type=file.content_type, reader=file
        )
    except IngestionError as exc:
        return _failure(request_id, _upload_error(exc.code, exc.message, exc.details))
    except IngestionStorageError:
        logger.exception("Storage failure while ingesting an upload")
        return _failure(request_id, _internal_error())
    except Exception:
        logger.exception("Unexpected failure while ingesting an upload")
        return _failure(request_id, _internal_error())
    finally:
        await file.close()

    body = SuccessResponse[IngestedDocument](
        request_id=request_id,
        message="Document uploaded successfully.",
        document_id=ingested.document_id,
        data=ingested,
        errors=[],
        meta={},
    )
    return JSONResponse(status_code=201, content=body.model_dump(mode="json"))
