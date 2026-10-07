"""Automated tests for NativePDFExtractor using deterministic PDF fixtures."""

import json
from pathlib import Path
import tempfile
import unittest

from backend.app.extractors.base import (
    BaseExtractor,
    NativePDFExtractor,
    PDFExtractionError,
    extract_pdf,
)
from backend.app.models.document import (
    BlockType,
    Document,
    ExtractorType,
    RiskLevel,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_PDF_PATH = FIXTURES_DIR / "sample_doc.pdf"


class TestNativePDFExtractor(unittest.TestCase):
    """Test suite for NativePDFExtractor and Document Graph output."""

    @classmethod
    def setUpClass(cls) -> None:
        if not SAMPLE_PDF_PATH.exists():
            raise FileNotFoundError(
                f"Required test fixture not found: {SAMPLE_PDF_PATH}"
            )
        cls.extractor = NativePDFExtractor()

    def test_implements_base_extractor(self) -> None:
        """Verify NativePDFExtractor inherits from BaseExtractor."""
        self.assertIsInstance(self.extractor, BaseExtractor)

    def test_pdf_parsing_and_page_count(self) -> None:
        """Verify the PDF parses successfully with correct metadata and page count."""
        doc = self.extractor.extract(SAMPLE_PDF_PATH, document_id="doc_test_fixture")

        self.assertIsInstance(doc, Document)
        self.assertEqual(doc.document_id, "doc_test_fixture")
        self.assertEqual(doc.filename, "sample_doc.pdf")
        self.assertEqual(doc.format, "pdf")
        self.assertEqual(doc.status, "completed")
        self.assertEqual(doc.page_count, 3)
        self.assertEqual(len(doc.pages), 3)

    def test_text_extraction_into_blocks(self) -> None:
        """Verify text content is properly extracted into Block objects."""
        doc = self.extractor.extract(SAMPLE_PDF_PATH)

        page1 = doc.pages[0]
        self.assertEqual(len(page1.blocks), 2)
        self.assertIn("Structura PDF Extractor Test", page1.blocks[0].content["text"])
        self.assertIn(
            "deterministic sample paragraph", page1.blocks[1].content["text"]
        )

        page2 = doc.pages[1]
        self.assertEqual(len(page2.blocks), 1)
        self.assertIn("Page two content block", page2.blocks[0].content["text"])

    def test_block_page_numbers_and_metadata(self) -> None:
        """Verify block page numbers, reading order, and block IDs."""
        doc = self.extractor.extract(SAMPLE_PDF_PATH)

        # Page 1 blocks
        for block in doc.pages[0].blocks:
            self.assertEqual(block.page, 1)
            self.assertEqual(block.type, BlockType.PARAGRAPH)
            self.assertEqual(block.risk.level, RiskLevel.LOW)
            self.assertTrue(block.traceable)

        self.assertEqual(doc.pages[0].blocks[0].reading_order, 1)
        self.assertEqual(doc.pages[0].blocks[1].reading_order, 2)
        self.assertEqual(doc.pages[0].blocks[0].id, "block_001")
        self.assertEqual(doc.pages[0].blocks[1].id, "block_002")

        # Page 2 blocks
        page2_block = doc.pages[1].blocks[0]
        self.assertEqual(page2_block.page, 2)
        self.assertEqual(page2_block.reading_order, 1)
        self.assertEqual(page2_block.id, "block_003")

    def test_extractor_type_identifier(self) -> None:
        """Verify all extracted blocks use the standardized native_pdf extractor identifier."""
        doc = self.extractor.extract(SAMPLE_PDF_PATH)
        all_blocks = [block for page in doc.pages for block in page.blocks]
        self.assertGreater(len(all_blocks), 0)

        for block in all_blocks:
            self.assertEqual(block.extractor, ExtractorType.NATIVE_PDF)

    def test_bounding_boxes_normalized(self) -> None:
        """Verify bounding boxes are normalized to [0.0, 1.0] with valid dimensions."""
        doc = self.extractor.extract(SAMPLE_PDF_PATH)
        all_blocks = [block for page in doc.pages for block in page.blocks]

        for block in all_blocks:
            bbox = block.bbox
            self.assertEqual(len(bbox), 4)
            x0, y0, x1, y1 = bbox
            for coord in (x0, y0, x1, y1):
                self.assertGreaterEqual(coord, 0.0)
                self.assertLessEqual(coord, 1.0)
            self.assertLessEqual(x0, x1)
            self.assertLessEqual(y0, y1)

    def test_empty_pages_preserved(self) -> None:
        """Verify empty pages are preserved in the Document Graph with zero blocks."""
        doc = self.extractor.extract(SAMPLE_PDF_PATH)

        page3 = doc.pages[2]
        self.assertEqual(page3.page, 3)
        self.assertEqual(page3.width, 612.0)
        self.assertEqual(page3.height, 792.0)
        self.assertEqual(len(page3.blocks), 0)

    def test_convenience_function(self) -> None:
        """Verify the extract_pdf helper produces a valid Document Graph."""
        doc = extract_pdf(SAMPLE_PDF_PATH)
        self.assertIsInstance(doc, Document)
        self.assertEqual(doc.page_count, 3)

    def test_error_handling_nonexistent_file(self) -> None:
        """Verify FileNotFoundError is raised for non-existent files."""
        with self.assertRaises(FileNotFoundError):
            self.extractor.extract("nonexistent_test_file.pdf")

    def test_error_handling_corrupt_file(self) -> None:
        """Verify PDFExtractionError is raised for corrupted files."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as corrupt_file:
            corrupt_file.write(b"not a valid pdf content")
            corrupt_path = Path(corrupt_file.name)

        try:
            with self.assertRaises(PDFExtractionError):
                self.extractor.extract(corrupt_path)
        finally:
            corrupt_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
