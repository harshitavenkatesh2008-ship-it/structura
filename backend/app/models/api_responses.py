"""Standard Structura API response contract (Checkpoint 8).

One envelope, four states, discriminated by `status`. Contract/validation
models only: no database calls, routing, retry/recovery execution, or file
processing. Internal engines return domain results; the API layer translates
them into these models later.
"""

from typing import Annotated, Generic, Literal, TypeVar, Union

from pydantic import Field, model_validator

from backend.app.models.api_base import ApiModel, JsonObject, NonEmptyStr
from backend.app.models.api_errors import ApiError
from backend.app.models.document_graph import Document

T = TypeVar("T")

NonNegativeInt = Annotated[int, Field(ge=0, strict=True)]
PositiveInt = Annotated[int, Field(gt=0, strict=True)]


# ---------------------------------------------------------------- processing
class Progress(ApiModel):
    """Counted progress. Never derived from elapsed time."""

    unit: NonEmptyStr
    completed: NonNegativeInt
    total: NonNegativeInt | None = None

    @model_validator(mode="after")
    def _completed_within_total(self) -> "Progress":
        if self.total is not None and self.completed > self.total:
            raise ValueError("completed must not exceed total")
        return self


class ProcessingData(ApiModel, Generic[T]):
    job_url: NonEmptyStr
    state: Literal["queued", "running", "retry_wait", "escalating"]
    stage: NonEmptyStr | None = None
    progress: Progress | None = None
    partial_result: T | None = None
    poll_after_seconds: PositiveInt
    parent_job_id: NonEmptyStr | None = None


# ---------------------------------------------------------- document results
class GraphReference(ApiModel):
    """Points at a stored graph. The revision lives in the API/storage layer,
    not inside Document Graph v1.0."""

    schema_version: Literal["1.0"] = "1.0"
    revision: NonEmptyStr
    url: NonEmptyStr


class ConfidenceSignal(ApiModel):
    value: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
    method: NonEmptyStr


class RiskSignal(ApiModel):
    level: Literal["low", "medium", "high"]
    method: NonEmptyStr


class QualitySummary(ApiModel):
    """Completeness and fidelity are separate concepts and never merged."""

    completeness: Literal["complete", "partial"]
    fidelity: Literal["pass", "fail", "not_evaluated"]
    confidence: ConfidenceSignal | None = None
    risk: RiskSignal | None = None


class DocumentResult(ApiModel):
    """Lightweight result: a reference to the graph, never the graph itself."""

    graph_ref: GraphReference
    quality: QualitySummary


class DocumentData(ApiModel):
    """Document retrieval payload: the existing Document Graph v1.0 model."""

    graph: Document
    graph_ref: GraphReference
    quality: QualitySummary


# ------------------------------------------------------------------ envelope
class _Envelope(ApiModel):
    """Fields common to all four variants. Subclasses add `status` and `data`."""

    response_version: Literal["1.0"] = "1.0"
    request_id: NonEmptyStr
    message: NonEmptyStr
    job_id: NonEmptyStr | None = None
    document_id: NonEmptyStr | None = None
    errors: list[ApiError] = Field(default_factory=list)
    meta: JsonObject = Field(default_factory=dict)


class SuccessResponse(_Envelope, Generic[T]):
    status: Literal["success"] = "success"
    data: T
    errors: list[ApiError] = Field(default_factory=list, max_length=0)

    @model_validator(mode="after")
    def _data_not_null(self) -> "SuccessResponse[T]":
        if self.data is None:
            raise ValueError("data must not be null for a success response")
        return self


class ProcessingResponse(_Envelope, Generic[T]):
    status: Literal["processing"] = "processing"
    job_id: NonEmptyStr  # required and non-null for this state
    data: ProcessingData[T]  # errors may be empty or hold unresolved issues


class PartialSuccessResponse(_Envelope, Generic[T]):
    status: Literal["partial_success"] = "partial_success"
    data: T
    errors: list[ApiError] = Field(min_length=1)

    @model_validator(mode="after")
    def _data_not_null(self) -> "PartialSuccessResponse[T]":
        if self.data is None:
            raise ValueError("data must not be null for a partial_success response")
        return self


class FailureResponse(_Envelope):
    status: Literal["failure"] = "failure"
    data: None = None  # always serialized as null
    errors: list[ApiError] = Field(min_length=1)


# Discriminated union keyed by `status`. Parametrize it, e.g.:
#   TypeAdapter(ApiResponse[DocumentData]).validate_python(payload)
type ApiResponse[T] = Annotated[
    Union[
        SuccessResponse[T],
        ProcessingResponse[T],
        PartialSuccessResponse[T],
        FailureResponse,
    ],
    Field(discriminator="status"),
]
