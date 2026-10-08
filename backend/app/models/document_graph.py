"""
Document Graph v1.0 — Pydantic models for Structura's common intermediate representation.

All extractors must convert their results into this schema before passing
data to another Structura component.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class BlockType(str, Enum):
    heading = "heading"
    paragraph = "paragraph"
    list = "list"
    table = "table"
    figure = "figure"
    chart = "chart"
    equation = "equation"
    image = "image"


class RiskLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class DocumentStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


# ---------------------------------------------------------------------------
# Risk
# ---------------------------------------------------------------------------

class Risk(BaseModel):
    model_config = {"extra": "forbid"}

    score: float = Field(..., ge=0.0, le=1.0)
    level: RiskLevel
    signals: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# BoundingBox — validated list of exactly 4 normalized floats
# ---------------------------------------------------------------------------

class BoundingBox(BaseModel):
    """
    Normalized bounding box: [x0, y0, x1, y1]
    All values in [0, 1].  x0 <= x1 and y0 <= y1.
    Degenerate boxes (x0==x1 or y0==y1) are allowed.
    """
    model_config = {"extra": "forbid"}

    values: List[float] = Field(..., min_length=4, max_length=4)

    @field_validator("values")
    @classmethod
    def validate_bbox(cls, v: List[float]) -> List[float]:
        if len(v) != 4:
            raise ValueError("bbox must contain exactly 4 values")
        x0, y0, x1, y1 = v
        for name, val in [("x0", x0), ("y0", y0), ("x1", x1), ("y1", y1)]:
            if not (0.0 <= val <= 1.0):
                raise ValueError(
                    f"bbox value '{name}'={val} is out of range [0, 1]"
                )
        if x0 > x1:
            raise ValueError(
                f"bbox x0={x0} must be <= x1={x1}"
            )
        if y0 > y1:
            raise ValueError(
                f"bbox y0={y0} must be <= y1={y1}"
            )
        return v

    @classmethod
    def from_list(cls, coords: List[float]) -> "BoundingBox":
        return cls(values=coords)

    def as_list(self) -> List[float]:
        return self.values


# ---------------------------------------------------------------------------
# Block
# ---------------------------------------------------------------------------

class Block(BaseModel):
    model_config = {"extra": "forbid"}

    id: str = Field(..., min_length=1)
    type: BlockType
    page: int = Field(..., ge=1)
    bbox: List[float] = Field(..., min_length=4, max_length=4)
    reading_order: int = Field(..., ge=0)
    content: dict[str, Any] = Field(default_factory=dict)
    extractor: str = Field(default="")
    risk: Optional[Risk] = None
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    flags: List[str] = Field(default_factory=list)
    traceable: bool = True
    parent: Optional[str] = None
    children: List[str] = Field(default_factory=list)

    @field_validator("bbox")
    @classmethod
    def validate_bbox(cls, v: List[float]) -> List[float]:
        if len(v) != 4:
            raise ValueError("bbox must contain exactly 4 values")
        x0, y0, x1, y1 = v
        for name, val in [("x0", x0), ("y0", y0), ("x1", x1), ("y1", y1)]:
            if not (0.0 <= val <= 1.0):
                raise ValueError(
                    f"bbox value '{name}'={val} is out of range [0, 1]"
                )
        if x0 > x1:
            raise ValueError(f"bbox x0={x0} must be <= x1={x1}")
        if y0 > y1:
            raise ValueError(f"bbox y0={y0} must be <= y1={y1}")
        return v


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

class Page(BaseModel):
    model_config = {"extra": "forbid"}

    page: int = Field(..., ge=1)
    width: float = Field(..., gt=0)
    height: float = Field(..., gt=0)
    blocks: List[Block] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

class Metrics(BaseModel):
    model_config = {"extra": "forbid"}

    processing_time_seconds: Optional[float] = Field(default=None, ge=0.0)
    pages_per_second: Optional[float] = Field(default=None, ge=0.0)
    provenance_coverage: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    escalated_regions_percent: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    estimated_cost_per_1000_pages: Optional[float] = Field(default=None, ge=0.0)
    cost_per_correct_page: Optional[float] = Field(default=None, ge=0.0)


# ---------------------------------------------------------------------------
# Document
# ---------------------------------------------------------------------------

class Document(BaseModel):
    model_config = {"extra": "forbid"}

    document_id: str = Field(..., min_length=1)
    filename: str = Field(default="")
    format: str = Field(default="")
    status: DocumentStatus = DocumentStatus.pending
    page_count: int = Field(default=0, ge=0)
    pages: List[Page] = Field(default_factory=list)
    metrics: Metrics = Field(default_factory=Metrics)
