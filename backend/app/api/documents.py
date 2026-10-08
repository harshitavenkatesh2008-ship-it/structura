"""Document retrieval, export, and telemetry API endpoints.

Provides:
- GET /v1/documents/{document_id} -> Full Document Graph JSON
- GET /v1/documents/{document_id}/markdown -> Formatted Markdown with block provenance
- GET /v1/documents/{document_id}/blocks -> Block list with spatial filtering
- GET /v1/documents/{document_id}/analytics -> Fidelity, risk distribution, and execution metrics
- POST /v1/documents/{document_id}/process -> Direct extraction execution for an uploaded file
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import JSONResponse, PlainTextResponse

from backend.app.core import error_codes
from backend.app.extractors.base import PDFExtractionError
from backend.app.models.api_errors import ApiError, RequestLocation
from backend.app.models.api_responses import (
    DocumentData,
    DocumentResult,
    FailureResponse,
    GraphReference,
    QualitySummary,
    SuccessResponse,
)
from backend.app.models.document_graph import Document
from backend.app.services.export_service import DocumentExportService
from backend.app.services.ingestion_service import DEFAULT_UPLOAD_ROOT, IngestionService
from backend.app.services.pipeline_service import PipelineService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["documents"])

# In-memory document storage cache for processed document graphs
_DOCUMENT_CACHE: Dict[str, Document] = {}
_PIPELINE_RESULTS_CACHE: Dict[str, Dict[str, Any]] = {}


def get_pipeline_service() -> PipelineService:
    return PipelineService()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def _doc_not_found_error(doc_id: str) -> ApiError:
    return ApiError(
        error_id=_new_id("err"),
        code=error_codes.DOCUMENT_UNAVAILABLE,
        category="request",
        message=f"Document with ID '{doc_id}' was not found or has not been processed.",
        recoverable=False,
        recovery=None,
        stage="retrieval",
        location=RequestLocation(field_path=["path", "document_id"]),
        details={"document_id": doc_id},
    )


def _process_error(code: str, message: str, details: Optional[dict] = None) -> ApiError:
    return ApiError(
        error_id=_new_id("err"),
        code=code,
        category="processing",
        message=message,
        recoverable=False,
        recovery=None,
        stage="extraction",
        details=details or {},
    )


@router.post("/documents/{document_id}/process", summary="Process an uploaded document through the SAFE extraction pipeline")
def process_document(
    document_id: str,
    pipeline: PipelineService = Depends(get_pipeline_service),
) -> JSONResponse:
    request_id = _new_id("req")

    # Locate the file in upload root
    candidate_paths = list(DEFAULT_UPLOAD_ROOT.glob(f"{document_id}.*"))
    valid_files = [p for p in candidate_paths if not p.name.endswith(".part")]

    if not valid_files:
        error = _doc_not_found_error(document_id)
        failure = FailureResponse(
            request_id=request_id,
            message=error.message,
            document_id=document_id,
            errors=[error],
        )
        return JSONResponse(status_code=404, content=failure.model_dump(mode="json"))

    target_file = valid_files[0]

    try:
        result = pipeline.process(target_file)
        doc: Document = result["document"]
        # Ensure document_id matches
        doc.document_id = document_id

        # Cache document graph and pipeline results
        _DOCUMENT_CACHE[document_id] = doc
        _PIPELINE_RESULTS_CACHE[document_id] = result

        graph_ref = GraphReference(
            schema_version="1.0",
            revision="1",
            url=f"/v1/documents/{document_id}",
        )
        quality = QualitySummary(
            completeness="complete",
            fidelity="pass" if result["status"] == "accept" else "fail",
        )
        doc_data = DocumentData(
            graph=doc,
            graph_ref=graph_ref,
            quality=quality,
        )

        success = SuccessResponse[DocumentData](
            request_id=request_id,
            message="Document processed successfully.",
            document_id=document_id,
            data=doc_data,
            errors=[],
            meta={"pipeline_status": result["status"], "block_count": result["block_count"]},
        )
        return JSONResponse(status_code=200, content=success.model_dump(mode="json"))

    except PDFExtractionError as exc:
        error = _process_error(error_codes.CORRUPT_DOCUMENT, f"Failed to parse document: {exc}", {"filename": target_file.name})
        failure = FailureResponse(request_id=request_id, message=error.message, document_id=document_id, errors=[error])
        return JSONResponse(status_code=422, content=failure.model_dump(mode="json"))
    except Exception as exc:
        logger.exception("Unexpected error during document processing: %s", exc)
        error = _process_error(error_codes.INTERNAL_ERROR, "An internal error occurred during document extraction.")
        failure = FailureResponse(request_id=request_id, message=error.message, document_id=document_id, errors=[error])
        return JSONResponse(status_code=500, content=failure.model_dump(mode="json"))


@router.get("/documents/{document_id}", summary="Retrieve the canonical Document Graph JSON")
def get_document_graph(document_id: str) -> JSONResponse:
    request_id = _new_id("req")
    doc = _DOCUMENT_CACHE.get(document_id)

    if doc is None:
        error = _doc_not_found_error(document_id)
        failure = FailureResponse(request_id=request_id, message=error.message, document_id=document_id, errors=[error])
        return JSONResponse(status_code=404, content=failure.model_dump(mode="json"))

    pipe_res = _PIPELINE_RESULTS_CACHE.get(document_id, {})
    graph_ref = GraphReference(schema_version="1.0", revision="1", url=f"/v1/documents/{document_id}")
    quality = QualitySummary(
        completeness="complete",
        fidelity="pass" if pipe_res.get("status") == "accept" else "fail",
    )
    doc_data = DocumentData(graph=doc, graph_ref=graph_ref, quality=quality)

    success = SuccessResponse[DocumentData](
        request_id=request_id,
        message="Document retrieved successfully.",
        document_id=document_id,
        data=doc_data,
        errors=[],
    )
    return JSONResponse(status_code=200, content=success.model_dump(mode="json"))


@router.get("/documents/{document_id}/markdown", summary="Export document to Markdown representation")
def get_document_markdown(document_id: str) -> Response:
    request_id = _new_id("req")
    doc = _DOCUMENT_CACHE.get(document_id)

    if doc is None:
        error = _doc_not_found_error(document_id)
        failure = FailureResponse(request_id=request_id, message=error.message, document_id=document_id, errors=[error])
        return JSONResponse(status_code=404, content=failure.model_dump(mode="json"))

    markdown_text = DocumentExportService.to_markdown(doc)
    return PlainTextResponse(content=markdown_text, media_type="text/markdown")


@router.get("/documents/{document_id}/blocks", summary="Query structured blocks with spatial bounding boxes")
def get_document_blocks(
    document_id: str,
    page: Optional[int] = Query(None, ge=1, description="Filter by page number"),
    type: Optional[str] = Query(None, description="Filter by block type"),
) -> JSONResponse:
    request_id = _new_id("req")
    doc = _DOCUMENT_CACHE.get(document_id)

    if doc is None:
        error = _doc_not_found_error(document_id)
        failure = FailureResponse(request_id=request_id, message=error.message, document_id=document_id, errors=[error])
        return JSONResponse(status_code=404, content=failure.model_dump(mode="json"))

    blocks = DocumentExportService.get_blocks(doc, page=page, block_type=type)
    success = SuccessResponse[List[Dict[str, Any]]](
        request_id=request_id,
        message="Blocks retrieved successfully.",
        document_id=document_id,
        data=blocks,
        errors=[],
        meta={"total_returned": len(blocks), "page_filter": page, "type_filter": type},
    )
    return JSONResponse(status_code=200, content=success.model_dump(mode="json"))


@router.get("/documents/{document_id}/analytics", summary="Retrieve extraction and fidelity telemetry")
def get_document_analytics(document_id: str) -> JSONResponse:
    request_id = _new_id("req")
    doc = _DOCUMENT_CACHE.get(document_id)

    if doc is None:
        error = _doc_not_found_error(document_id)
        failure = FailureResponse(request_id=request_id, message=error.message, document_id=document_id, errors=[error])
        return JSONResponse(status_code=404, content=failure.model_dump(mode="json"))

    pipe_res = _PIPELINE_RESULTS_CACHE.get(document_id)
    analytics = DocumentExportService.compute_analytics(doc, pipeline_result=pipe_res)

    success = SuccessResponse[Dict[str, Any]](
        request_id=request_id,
        message="Analytics computed successfully.",
        document_id=document_id,
        data=analytics,
        errors=[],
    )
    return JSONResponse(status_code=200, content=success.model_dump(mode="json"))
