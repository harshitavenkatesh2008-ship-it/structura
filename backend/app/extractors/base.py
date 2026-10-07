"""Base extractor module for the Structura universal document ingestion engine.

Provides the foundational extractor interface and the NativePDFExtractor
implementation for extracting structured Document Graph v1.0 objects from
native digital PDF files.
"""

from abc import ABC, abstractmethod
from pathlib import Path
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
    """Basic native digital PDF extractor for Structura.

    Extracts text blocks and spatial bounding boxes from digital PDFs using
    PyMuPDF, mapping the extracted hierarchy into Structura Document Graph v1.0.
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

    def extract(self, file_path: Union[str, Path], **kwargs: Any) -> Document:
        """Extract text blocks from a PDF file into a Structura Document Graph.

        Args:
            file_path: Path to the PDF file on disk.
            **kwargs:
                document_id: Optional custom identifier for the document.

        Returns:
            Document: Document Graph containing extracted pages and blocks.

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

                pages: list[Page] = []
                block_counter = 0

                for page_idx in range(len(pdf_doc)):
                    pdf_page = pdf_doc[page_idx]
                    page_num = page_idx + 1
                    width = float(pdf_page.rect.width)
                    height = float(pdf_page.rect.height)

                    raw_blocks = pdf_page.get_text("blocks")
                    page_blocks: list[Block] = []
                    reading_order = 1

                    for raw in raw_blocks:
                        # PyMuPDF block tuple: (x0, y0, x1, y1, text, block_no, block_type)
                        # block_type 0 = text, 1 = image
                        if len(raw) < 7:
                            continue

                        x0, y0, x1, y1, text, _, block_type = raw[:7]

                        # Process text blocks with non-empty content
                        if block_type == 0 and isinstance(text, str) and text.strip():
                            block_counter += 1
                            bbox = self._normalize_bbox(x0, y0, x1, y1, width, height)

                            block = Block(
                                id=f"block_{block_counter:03d}",
                                type=BlockType.PARAGRAPH,
                                page=page_num,
                                bbox=bbox,
                                reading_order=reading_order,
                                content={"text": text.strip()},
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
