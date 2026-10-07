"""Structured API error models (Checkpoint 8).

Contract/validation only: nothing here executes recovery, retries, or maps
errors to HTTP status codes.
"""

from typing import Annotated, Literal, Union

from pydantic import Field, StrictBool, StringConstraints, model_validator

from backend.app.models.api_base import ApiModel, JsonObject, NonEmptyStr

# Public error codes are an OPEN string contract. New codes may be added
# without breaking older clients, so this is a pattern, not an enum.
ERROR_CODE_PATTERN = r"^[A-Z][A-Z0-9_]{0,63}$"
ErrorCode = Annotated[str, StringConstraints(pattern=ERROR_CODE_PATTERN)]

ErrorCategory = Literal["request", "processing", "quality", "dependency", "internal"]

PageNumber = Annotated[int, Field(ge=1, strict=True)]


class RecoveryHint(ApiModel):
    """Advice about recovery. Describes it; never performs it."""

    action: Literal["retry", "escalate"]
    owner: Literal["server", "client"]
    retry_after_seconds: Annotated[int, Field(ge=0, strict=True)] | None = None

    @model_validator(mode="after")
    def _escalation_has_no_retry_delay(self) -> "RecoveryHint":
        if self.action == "escalate" and self.retry_after_seconds is not None:
            raise ValueError("retry_after_seconds must be null when action is 'escalate'")
        return self


class _GraphLocated(ApiModel):
    """Optional Document Graph locator shared by document/page/region scopes.

    The revision belongs to the API/storage layer, not to Document Graph v1.0.
    No bounding-box fields: geometry stays in the Document Graph conventions.
    """

    graph_revision: NonEmptyStr | None = None
    graph_pointer: NonEmptyStr | None = None

    @model_validator(mode="after")
    def _pointer_requires_revision(self) -> "_GraphLocated":
        if self.graph_pointer is not None and self.graph_revision is None:
            raise ValueError("graph_pointer requires graph_revision")
        return self


class RequestLocation(ApiModel):
    scope: Literal["request"] = "request"
    # Ordered path segments, e.g. ["body", "file"]. A list, not a dotted string.
    field_path: Annotated[list[NonEmptyStr], Field(min_length=1)]


class DocumentLocation(_GraphLocated):
    scope: Literal["document"] = "document"
    document_id: NonEmptyStr


class PageLocation(_GraphLocated):
    scope: Literal["page"] = "page"
    document_id: NonEmptyStr
    page_number: PageNumber  # one-based


class RegionLocation(_GraphLocated):
    scope: Literal["region"] = "region"
    document_id: NonEmptyStr
    page_number: PageNumber  # one-based
    region_id: NonEmptyStr


ErrorLocation = Annotated[
    Union[RequestLocation, DocumentLocation, PageLocation, RegionLocation],
    Field(discriminator="scope"),
]


class ApiError(ApiModel):
    """The one reusable structured error.

    `message` must be safe for clients: no stack traces, credentials, SQL,
    local paths, raw provider payloads, or document contents. That is the
    responsibility of the API layer that builds the error; the model only
    enforces shape.
    """

    error_id: NonEmptyStr
    code: ErrorCode
    category: ErrorCategory
    message: NonEmptyStr
    recoverable: StrictBool
    recovery: RecoveryHint | None = None
    stage: NonEmptyStr | None = None
    location: ErrorLocation | None = None
    details: JsonObject = Field(default_factory=dict)

    @model_validator(mode="after")
    def _recovery_matches_recoverable(self) -> "ApiError":
        if self.recoverable and self.recovery is None:
            raise ValueError("recovery is required when recoverable is true")
        if not self.recoverable and self.recovery is not None:
            raise ValueError("recovery must be null when recoverable is false")
        return self
