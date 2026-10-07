from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator


class BlockType(str, Enum):
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST = "list"
    TABLE = "table"
    FIGURE = "figure"
    CHART = "chart"
    EQUATION = "equation"
    IMAGE = "image"


class ExtractorType(str, Enum):
    NATIVE_PDF = "native_pdf"
    OCR = "ocr"
    TABLE_ENGINE = "table_engine"
    VISION_ENGINE = "vision_engine"
    MATH_ENGINE = "math_engine"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RiskInfo(BaseModel):
    score: float = 0.0
    level: RiskLevel = RiskLevel.LOW
    signals: list[str] = Field(default_factory=list)


class DocumentMetrics(BaseModel):
    processing_time_seconds: Optional[float] = None
    pages_per_second: Optional[float] = None
    provenance_coverage: Optional[float] = None
    escalated_regions_percent: Optional[float] = None
    estimated_cost_per_1000_pages: Optional[float] = None
    cost_per_correct_page: Optional[float] = None


class Block(BaseModel):
    id: str
    type: BlockType
    page: int
    bbox: list[float]
    reading_order: int
    content: dict[str, Any]
    extractor: ExtractorType
    risk: RiskInfo = Field(default_factory=RiskInfo)
    confidence: Optional[float] = None
    flags: list[str] = Field(default_factory=list)
    traceable: bool = True
    parent: Optional[str] = None
    children: list[str] = Field(default_factory=list)

    @field_validator("bbox")
    @classmethod
    def validate_bbox(cls, v: list[float]) -> list[float]:
        if len(v) != 4:
            raise ValueError("Bounding box must contain exactly 4 coordinates: [x0, y0, x1, y1].")
        for coord in v:
            if not (0.0 <= coord <= 1.0):
                raise ValueError(f"Bounding box coordinate {coord} is outside the allowed range [0.0, 1.0].")
        return v


class Page(BaseModel):
    page: int
    width: float
    height: float
    blocks: list[Block] = Field(default_factory=list)


class Document(BaseModel):
    document_id: str
    filename: str
    format: str
    status: str = "processing"
    page_count: int
    pages: list[Page] = Field(default_factory=list)
    metrics: DocumentMetrics = Field(default_factory=DocumentMetrics)
