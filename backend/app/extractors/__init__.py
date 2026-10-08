"""Extractors module for Structura.

Exports the foundational BaseExtractor interface and the NativePDFExtractor
implementation for structured Document Graph extraction.
"""

from backend.app.extractors.base import (
    BaseExtractor,
    NativePDFExtractor,
    PDFExtractionError,
    extract_pdf,
)

__all__ = [
    "BaseExtractor",
    "NativePDFExtractor",
    "PDFExtractionError",
    "extract_pdf",
]
