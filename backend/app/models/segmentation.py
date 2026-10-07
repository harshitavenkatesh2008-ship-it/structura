
from typing import Literal

from pydantic import BaseModel, Field, model_validator


SegmentType = Literal[
    "page",
    "section",
    "heading",
    "paragraph",
    "list",
    "table",
    "figure",
    "chart",
    "equation",
    "image",
    "worksheet",
    "slide",
    "cell_range",
    "unknown",
]


class Segment(BaseModel):
    segment_id: str = Field(min_length=1)
    segment_type: SegmentType
    reading_order: int = Field(ge=0)
    page: int | None = Field(default=None, ge=1)
    parent_id: str | None = None
    source_block_ids: list[str] = Field(default_factory=list)
    text: str | None = None
    bbox: tuple[float, float, float, float] | None = None

    @model_validator(mode="after")
    def validate_bbox(self):
        if self.bbox is not None:
            x0, y0, x1, y1 = self.bbox
            if not all(0 <= value <= 1 for value in self.bbox):
                raise ValueError("bbox coordinates must be normalized")
            if x0 > x1 or y0 > y1:
                raise ValueError("bbox coordinates are inverted")
        return self


class SegmentedDocument(BaseModel):
    document_id: str = Field(min_length=1)
    segments: list[Segment] = Field(default_factory=list)
    segment_count: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_segments(self):
        if self.segment_count != len(self.segments):
            raise ValueError("segment_count must match segments length")

        ids = [segment.segment_id for segment in self.segments]
        if len(ids) != len(set(ids)):
            raise ValueError("segment IDs must be unique")

        return self
