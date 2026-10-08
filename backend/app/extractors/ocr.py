"""OCR extractor module for Structura.

Provides region-level and page-level OCR extraction using PyMuPDF / Tesseract,
with automatic capability detection and graceful degradation when OCR dependencies
are not present on the host system.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

import pymupdf

logger = logging.getLogger(__name__)


def is_ocr_available() -> bool:
    """Check if PyMuPDF has a working Tesseract OCR backend available."""
    try:
        doc = pymupdf.open()
        page = doc.new_page(width=100, height=100)
        # Test creating an OCR textpage on an empty in-memory page
        _ = page.get_textpage_ocr(dpi=72)
        doc.close()
        return True
    except Exception:
        return False


class OCRExtractor:
    """Specialist OCR extractor capable of region-level extraction.

    Extracts text from scanned pages or image regions. When Tesseract is
    unavailable, reports structured failure without crashing the pipeline.
    """

    EXTRACTOR_NAME = "ocr"

    def __init__(self, force_available: Optional[bool] = None) -> None:
        if force_available is not None:
            self._available = force_available
        else:
            self._available = is_ocr_available()

    @property
    def is_available(self) -> bool:
        return self._available

    def extract_region(
        self,
        file_path: Union[str, Path],
        page: int,
        bbox: Union[Tuple[float, float, float, float], list[float]],
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Extract text from a normalized bounding box [x0, y0, x1, y1] on 1-based page.

        Returns a dictionary representing extraction outcome:
        {
            "success": bool,
            "text": str,
            "confidence": Optional[float],
            "flags": list[str],
            "error": Optional[str],
        }
        """
        if not self._available:
            return {
                "success": False,
                "text": "",
                "confidence": None,
                "flags": ["OCR_UNAVAILABLE"],
                "error": "OCR engine (Tesseract) is not available or configured on system.",
            }

        path = Path(file_path)
        if not path.is_file():
            return {
                "success": False,
                "text": "",
                "confidence": None,
                "flags": ["FILE_NOT_FOUND"],
                "error": f"File not found: {path}",
            }

        try:
            with pymupdf.open(str(path)) as doc:
                page_idx = page - 1
                if page_idx < 0 or page_idx >= len(doc):
                    return {
                        "success": False,
                        "text": "",
                        "confidence": None,
                        "flags": ["INVALID_PAGE"],
                        "error": f"Page index {page} out of bounds (1-{len(doc)})",
                    }

                pdf_page = doc[page_idx]
                width = float(pdf_page.rect.width)
                height = float(pdf_page.rect.height)

                # Convert normalized [x0, y0, x1, y1] back to absolute points
                x0, y0, x1, y1 = bbox
                rect = pymupdf.Rect(x0 * width, y0 * height, x1 * width, y1 * height)

                # PyMuPDF clip rect OCR
                textpage = pdf_page.get_textpage_ocr(flags=0, dpi=150, clip=rect)
                text = pdf_page.get_text(textpage=textpage, clip=rect).strip()

                return {
                    "success": True,
                    "text": text,
                    "confidence": 0.85 if text else 0.5,
                    "flags": [],
                    "error": None,
                }
        except Exception as exc:
            logger.exception("OCR extraction failed on page %d bbox %s: %s", page, bbox, exc)
            return {
                "success": False,
                "text": "",
                "confidence": None,
                "flags": ["OCR_EXECUTION_FAILED"],
                "error": str(exc),
            }
