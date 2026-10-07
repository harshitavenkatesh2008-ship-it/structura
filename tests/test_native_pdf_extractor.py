"""Automated tests for NativePDFExtractor using deterministic PDF fixtures."""

import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
import pymupdf

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
        self.assertGreaterEqual(len(page1.blocks), 4)

        # Check expected text contents across page 1 blocks
        texts = [b.content.get("text", "") for b in page1.blocks]
        self.assertTrue(
            any("Structura PDF Extractor Test" in t for t in texts)
        )
        self.assertTrue(
            any("deterministic sample paragraph" in t for t in texts)
        )

        page2 = doc.pages[1]
        self.assertEqual(len(page2.blocks), 1)
        self.assertIn("Page two content block", page2.blocks[0].content["text"])

    def test_heading_classification(self) -> None:
        """Verify that large/bold title text is classified as HEADING."""
        doc = self.extractor.extract(SAMPLE_PDF_PATH)
        page1 = doc.pages[0]

        heading_blocks = [b for b in page1.blocks if b.type == BlockType.HEADING]
        self.assertGreaterEqual(len(heading_blocks), 1)
        self.assertIn("Structura PDF Extractor Test", heading_blocks[0].content["text"])

    def test_paragraph_classification(self) -> None:
        """Verify that standard body text is classified as PARAGRAPH."""
        doc = self.extractor.extract(SAMPLE_PDF_PATH)
        page1 = doc.pages[0]

        paragraph_blocks = [b for b in page1.blocks if b.type == BlockType.PARAGRAPH]
        self.assertGreaterEqual(len(paragraph_blocks), 1)
        self.assertIn("deterministic sample paragraph", paragraph_blocks[0].content["text"])

        # Page 2 content should also be PARAGRAPH
        page2 = doc.pages[1]
        self.assertEqual(page2.blocks[0].type, BlockType.PARAGRAPH)

    def test_list_classification(self) -> None:
        """Verify that bullet and numbered items are classified as LIST."""
        doc = self.extractor.extract(SAMPLE_PDF_PATH)
        page1 = doc.pages[0]

        list_blocks = [b for b in page1.blocks if b.type == BlockType.LIST]
        self.assertGreaterEqual(len(list_blocks), 2)
        list_texts = [b.content["text"] for b in list_blocks]
        self.assertTrue(any("First feature" in t for t in list_texts))
        self.assertTrue(any("Second feature" in t for t in list_texts))

    def test_image_classification(self) -> None:
        """Verify that embedded raster images are detected and classified as IMAGE."""
        doc = self.extractor.extract(SAMPLE_PDF_PATH)
        page1 = doc.pages[0]

        image_blocks = [b for b in page1.blocks if b.type == BlockType.IMAGE]
        self.assertEqual(len(image_blocks), 1)
        self.assertEqual(image_blocks[0].content.get("type"), "image")
        self.assertEqual(image_blocks[0].page, 1)

    def test_block_page_numbers_and_metadata(self) -> None:
        """Verify block page numbers, reading order, and block IDs."""
        doc = self.extractor.extract(SAMPLE_PDF_PATH)

        # Page 1 blocks
        for block in doc.pages[0].blocks:
            self.assertEqual(block.page, 1)
            self.assertEqual(block.risk.level, RiskLevel.LOW)
            self.assertTrue(block.traceable)

        # Verify sequential reading order on page 1
        for i, block in enumerate(doc.pages[0].blocks):
            self.assertEqual(block.reading_order, i + 1)
            self.assertEqual(block.id, f"block_{i + 1:03d}")

        # Page 2 block
        page2_block = doc.pages[1].blocks[0]
        self.assertEqual(page2_block.page, 2)
        self.assertEqual(page2_block.reading_order, 1)
        self.assertEqual(page2_block.id, f"block_{len(doc.pages[0].blocks) + 1:03d}")

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

    def test_normal_block_risk_baseline(self) -> None:
        """Verify normal text blocks maintain LOW risk with score 0.0, no signals, and no flags."""
        doc = self.extractor.extract(SAMPLE_PDF_PATH)
        page1 = doc.pages[0]

        normal_blocks = [
            b for b in page1.blocks if b.type in (BlockType.PARAGRAPH, BlockType.HEADING)
        ]
        self.assertGreater(len(normal_blocks), 0)
        for block in normal_blocks:
            self.assertEqual(block.risk.level, RiskLevel.LOW)
            self.assertEqual(block.risk.score, 0.0)
            self.assertEqual(block.risk.signals, [])
            self.assertEqual(block.flags, [])

    def test_encoding_anomaly_detector_heuristic(self) -> None:
        """Verify the encoding anomaly detector identifies U+FFFD and PUA characters."""
        self.assertTrue(NativePDFExtractor._detect_encoding_anomalies("Unmapped \ufffd char"))
        self.assertTrue(NativePDFExtractor._detect_encoding_anomalies("Private use \ue001 glyph"))
        self.assertFalse(NativePDFExtractor._detect_encoding_anomalies("Standard text with • bullet"))
        self.assertFalse(NativePDFExtractor._detect_encoding_anomalies("Latin with accents: café, naïve"))

    def test_encoding_anomaly_detection_on_extraction(self) -> None:
        """Verify U+FFFD triggers RiskLevel.MEDIUM, font_encoding_anomaly, and ENCODING_DEGRADATION."""
        corrupted_text = "Corrupted text \ufffd with unmapped glyph"
        mock_layout = {
            "blocks": [
                {
                    "type": 0,
                    "bbox": (72.0, 72.0, 300.0, 90.0),
                    "lines": [
                        {
                            "spans": [
                                {
                                    "text": corrupted_text,
                                    "size": 11.0,
                                    "flags": 0,
                                    "font": "Helvetica",
                                }
                            ]
                        }
                    ],
                }
            ]
        }

        with patch("pymupdf.Page.get_text", return_value=mock_layout):
            doc = self.extractor.extract(SAMPLE_PDF_PATH)
            block = doc.pages[0].blocks[0]

            # Verify text is preserved verbatim without modification
            self.assertEqual(block.content["text"], corrupted_text)
            # Verify elevated risk and evidence signals/flags
            self.assertEqual(block.risk.level, RiskLevel.MEDIUM)
            self.assertEqual(block.risk.score, 0.0)
            self.assertIn("font_encoding_anomaly", block.risk.signals)
            self.assertIn("ENCODING_DEGRADATION", block.flags)

    def test_scanned_image_only_page_detection(self) -> None:
        """Verify scanned/image-only pages preserve IMAGE blocks with SCANNED_CONTENT_DETECTED flag."""
        # Create minimal PNG in memory
        img = Image.new("RGB", (80, 80), color="gray")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        img_bytes = buf.getvalue()

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            pdf_doc = pymupdf.open()
            page = pdf_doc.new_page(width=612, height=792)
            # Scanned page: only an image, no text blocks
            page.insert_image(pymupdf.Rect(50, 50, 562, 742), stream=img_bytes)
            pdf_doc.save(str(tmp_path))
            pdf_doc.close()

            doc = self.extractor.extract(tmp_path)
            self.assertEqual(doc.page_count, 1)
            self.assertEqual(len(doc.pages[0].blocks), 1)

            image_block = doc.pages[0].blocks[0]
            self.assertEqual(image_block.type, BlockType.IMAGE)
            self.assertIn("SCANNED_CONTENT_DETECTED", image_block.flags)
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_blank_page_not_flagged_as_scanned(self) -> None:
        """Verify genuinely blank pages have zero blocks and are not flagged as scanned content."""
        doc = self.extractor.extract(SAMPLE_PDF_PATH)
        page3 = doc.pages[2]

        self.assertEqual(page3.page, 3)
        self.assertEqual(len(page3.blocks), 0)

        # Embedded image on page with text should NOT have SCANNED_CONTENT_DETECTED
        page1_images = [b for b in doc.pages[0].blocks if b.type == BlockType.IMAGE]
        self.assertEqual(len(page1_images), 1)
        self.assertNotIn("SCANNED_CONTENT_DETECTED", page1_images[0].flags)

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
