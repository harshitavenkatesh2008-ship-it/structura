"""Ingestion payload model (Checkpoint 9).

Describes an uploaded artifact only. It does not duplicate the Document Graph.
"""

import re
from typing import Annotated, Literal

from pydantic import Field, field_validator

from backend.app.models.api_base import ApiModel, NonEmptyStr

IngestionFormat = Literal["pdf", "xlsx", "pptx", "png", "jpg", "jpeg", "tiff"]

_DRIVE_PREFIX = re.compile(r"^[A-Za-z]:")


class IngestedDocument(ApiModel):
    document_id: NonEmptyStr
    filename: NonEmptyStr  # client filename, directory components removed
    format: IngestionFormat
    content_type: NonEmptyStr
    size_bytes: Annotated[int, Field(gt=0, strict=True)]
    status: Literal["pending"] = "pending"
    storage_key: NonEmptyStr  # relative logical key, e.g. "uploads/<id>.pdf"

    @field_validator("storage_key")
    @classmethod
    def _storage_key_is_relative(cls, value: str) -> str:
        if (
            value.startswith(("/", "\\"))
            or "\\" in value
            or _DRIVE_PREFIX.match(value)
            or ".." in value.split("/")
        ):
            raise ValueError("storage_key must be a relative logical key")
        return value
