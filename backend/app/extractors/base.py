"""Base extractor module for the Structura universal document ingestion engine.

Provides the foundational extractor interface and the NativePDFExtractor
implementation for extracting structured Document Graph v1.0 objects from
native digital PDF files with structural block type classification.
"""

from abc import ABC, abstractmethod
from collections import Counter
from pathlib import Path
import re
import time
from typing import Any, Optional, Union
import uuid

import pymupdf

from backend.app.models.document import (
    Block,
    BlockType,
    Document,
    DocumentMetrics,
    ExtractorType,
    Page,
    RiskInfo,
    RiskLevel,
)

# Common prefixes for bulleted and numbered lists
LIST_PREFIX_PATTERN = re.compile(
    r"^("
    r"[•\-\*\u2022\u2023\u25E6\u2043\u2219\ufffd]|"
    r"(?:\d+|[a-zA-Z])[\.\)]|"
    r"\((?:\d+|[a-zA-Z])\)"
    r")\s+"
)


class ExtractorError(Exception):
    """Base exception for extraction failures."""
    pass


class PDFExtractionError(ExtractorError):
    """Raised when PDF extraction fails due to invalid, corrupt, or unreadable files."""
    pass


class BaseExtractor(ABC):
    """Abstract base class for all Structura extractors."""

    @abstractmethod
    def extract(self, file_path: Union[str, Path], **kwargs: Any) -> Document:
        """Extract content from a file and return a Document Graph representation.

        Args:
            file_path: Path to the target document.
            **kwargs: Additional extractor-specific options.

        Returns:
            Document: Validated Document Graph v1.0 object.

        Raises:
            ExtractorError: If the document cannot be processed.
        """
        pass


class NativePDFExtractor(BaseExtractor):
    """Native digital PDF extractor for Structura.

    Extracts text and image blocks, calculates normalized spatial bounding boxes,
    and applies typographic and syntactical heuristics to classify blocks into
    HEADING, LIST, PARAGRAPH, and IMAGE types according to Document Graph v1.0.
    """

    def __init__(self) -> None:
        pass

    @staticmethod
    def _normalize_bbox(
        x0: float, y0: float, x1: float, y1: float, width: float, height: float
    ) -> list[float]:
        """Normalize coordinates to [x0, y0, x1, y1] within [0.0, 1.0].

        Bounding boxes use (0,0) as the top-left origin per Document Graph v1.0.
        """
        if width <= 0 or height <= 0:
            return [0.0, 0.0, 0.0, 0.0]

        nx0 = max(0.0, min(1.0, round(x0 / width, 4)))
        ny0 = max(0.0, min(1.0, round(y0 / height, 4)))
        nx1 = max(0.0, min(1.0, round(x1 / width, 4)))
        ny1 = max(0.0, min(1.0, round(y1 / height, 4)))

        # Ensure x0 <= x1 and y0 <= y1
        if nx0 > nx1:
            nx0, nx1 = nx1, nx0
        if ny0 > ny1:
            ny0, ny1 = ny1, ny0

        return [nx0, ny0, nx1, ny1]

    @staticmethod
    def _calculate_body_font_size(pdf_doc: pymupdf.Document) -> float:
        """Determine the dominant (body) font size across all text spans in the PDF."""
        sizes: list[float] = []
        for page in pdf_doc:
            page_dict = page.get_text("dict")
            for block in page_dict.get("blocks", []):
                if block.get("type") == 0:
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            if span.get("text", "").strip():
                                sizes.append(round(float(span.get("size", 11.0)), 1))
        if not sizes:
            return 11.0
        counts = Counter(sizes)
        return counts.most_common(1)[0][0]

    @staticmethod
    def _classify_text_block(
        text: str,
        font_size: float,
        is_bold: bool,
        body_font_size: float,
        line_count: int,
    ) -> BlockType:
        """Classify a text block into HEADING, LIST, or PARAGRAPH.

        Args:
            text: Raw extracted text of the block.
            font_size: Dominant font size of the block.
            is_bold: True if the block contains bold spans.
            body_font_size: Document-wide baseline body font size.
            line_count: Number of lines in the block.

        Returns:
            BlockType: Structural block classification.
        """
        stripped = text.strip()
        if not stripped:
            return BlockType.PARAGRAPH

        # Detect list items by bullet or numerical/alphabetical prefix
        if LIST_PREFIX_PATTERN.match(stripped):
            return BlockType.LIST

        # Detect headings: must be concise and distinctly styled
        is_concise = len(stripped) <= 200 and line_count <= 3
        is_significantly_larger = font_size >= body_font_size * 1.2
        is_bold_heading = is_bold and (
            font_size >= body_font_size * 1.1
            or (line_count == 1 and len(stripped) < 80 and not stripped.endswith("."))
        )

        if is_concise and (is_significantly_larger or is_bold_heading):
            return BlockType.HEADING

        return BlockType.PARAGRAPH

    def extract(self, file_path: Union[str, Path], **kwargs: Any) -> Document:
        """Extract text and image blocks from a PDF into a Structura Document Graph.

        Args:
            file_path: Path to the PDF file on disk.
            **kwargs:
                document_id: Optional custom identifier for the document.

        Returns:
            Document: Document Graph containing extracted pages and classified blocks.

        Raises:
            FileNotFoundError: If the input file does not exist.
            ValueError: If the input path points to a directory or is not a regular file.
            PDFExtractionError: If the PDF cannot be opened, is encrypted, or is corrupted.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF file not found: {path}")
        if not path.is_file():
            raise ValueError(f"Path is not a regular file: {path}")

        start_time = time.perf_counter()
        doc_id = kwargs.get("document_id") or f"doc_{uuid.uuid4().hex[:8]}"

        try:
            with pymupdf.open(str(path)) as pdf_doc:
                if pdf_doc.is_encrypted:
                    raise PDFExtractionError(
                        f"PDF '{path.name}' is encrypted or password-protected."
                    )

                body_font_size = self._calculate_body_font_size(pdf_doc)
                pages: list[Page] = []
                block_counter = 0

                for page_idx in range(len(pdf_doc)):
                    pdf_page = pdf_doc[page_idx]
                    page_num = page_idx + 1
                    width = float(pdf_page.rect.width)
                    height = float(pdf_page.rect.height)

                    page_dict = pdf_page.get_text("dict")
                    raw_blocks = page_dict.get("blocks", [])
                    page_blocks: list[Block] = []
                    reading_order = 1

                    for raw in raw_blocks:
                        block_type_code = raw.get("type", 0)

                        # Process text blocks (type 0)
                        if block_type_code == 0:
                            line_texts: list[str] = []
                            block_sizes: list[float] = []
                            is_bold = False

                            for line in raw.get("lines", []):
                                line_str = "".join(
                                    span.get("text", "")
                                    for span in line.get("spans", [])
                                )
                                if line_str.strip():
                                    line_texts.append(line_str)

                                for span in line.get("spans", []):
                                    span_text = span.get("text", "").strip()
                                    if span_text:
                                        block_sizes.append(
                                            float(span.get("size", 11.0))
                                        )
                                        flags = int(span.get("flags", 0))
                                        font_name = str(
                                            span.get("font", "")
                                        ).lower()
                                        if (flags & 16 != 0) or ("bold" in font_name):
                                            is_bold = True

                            full_text = "\n".join(line_texts).strip()
                            if not full_text:
                                continue

                            block_counter += 1
                            x0, y0, x1, y1 = raw.get("bbox", (0, 0, 0, 0))[:4]
                            bbox = self._normalize_bbox(x0, y0, x1, y1, width, height)

                            dominant_font_size = (
                                max(block_sizes) if block_sizes else body_font_size
                            )
                            block_type = self._classify_text_block(
                                text=full_text,
                                font_size=dominant_font_size,
                                is_bold=is_bold,
                                body_font_size=body_font_size,
                                line_count=len(line_texts),
                            )

                            block = Block(
                                id=f"block_{block_counter:03d}",
                                type=block_type,
                                page=page_num,
                                bbox=bbox,
                                reading_order=reading_order,
                                content={"text": full_text},
                                extractor=ExtractorType.NATIVE_PDF,
                                risk=RiskInfo(
                                    score=0.0,
                                    level=RiskLevel.LOW,
                                    signals=[],
                                ),
                                confidence=None,
                                flags=[],
                                traceable=True,
                                parent=None,
                                children=[],
                            )
                            page_blocks.append(block)
                            reading_order += 1

                        # Process image blocks (type 1)
                        elif block_type_code == 1:
                            block_counter += 1
                            x0, y0, x1, y1 = raw.get("bbox", (0, 0, 0, 0))[:4]
                            bbox = self._normalize_bbox(x0, y0, x1, y1, width, height)

                            block = Block(
                                id=f"block_{block_counter:03d}",
                                type=BlockType.IMAGE,
                                page=page_num,
                                bbox=bbox,
                                reading_order=reading_order,
                                content={"text": "", "type": "image"},
                                extractor=ExtractorType.NATIVE_PDF,
                                risk=RiskInfo(
                                    score=0.0,
                                    level=RiskLevel.LOW,
                                    signals=[],
                                ),
                                confidence=None,
                                flags=[],
                                traceable=True,
                                parent=None,
                                children=[],
                            )
                            page_blocks.append(block)
                            reading_order += 1

                    pages.append(
                        Page(
                            page=page_num,
                            width=width,
                            height=height,
                            blocks=page_blocks,
                        )
                    )

        except (FileNotFoundError, ValueError, PDFExtractionError):
            raise
        except Exception as exc:
            raise PDFExtractionError(
                f"Failed to extract PDF '{path.name}': {exc}"
            ) from exc

        elapsed = round(time.perf_counter() - start_time, 4)
        pages_per_sec = round(len(pages) / elapsed, 2) if elapsed > 0 else None

        metrics = DocumentMetrics(
            processing_time_seconds=elapsed,
            pages_per_second=pages_per_sec,
        )

        return Document(
            document_id=doc_id,
            filename=path.name,
            format="pdf",
            status="completed",
            page_count=len(pages),
            pages=pages,
            metrics=metrics,
        )


def extract_pdf(file_path: Union[str, Path], **kwargs: Any) -> Document:
    """Convenience helper to extract a PDF file using NativePDFExtractor."""
    extractor = NativePDFExtractor()
    return extractor.extract(file_path, **kwargs)
