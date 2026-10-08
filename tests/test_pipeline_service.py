
"""Tests for the C11 pipeline integration service."""

from unittest.mock import patch

import pytest

from backend.app.models import document as source
from backend.app.services.pipeline_service import PipelineService


def make_document(text="Hello STRUCTURA"):
    """Create a small extracted document for testing."""

    block = source.Block(
        id="block_1",
        type=source.BlockType.PARAGRAPH,
        page=1,
        bbox=[0.1, 0.2, 0.8, 0.9],
        reading_order=0,
        content={"text": text},
        extractor=source.ExtractorType.NATIVE_PDF,
        confidence=0.95,
    )

    page = source.Page(
        page=1,
        width=612,
        height=792,
        blocks=[block],
    )

    return source.Document(
        document_id="doc_1",
        filename="sample.pdf",
        format="pdf",
        page_count=1,
        pages=[page],
    )


class FakeExtractor:
    """Avoid needing a real PDF in unit tests."""

    def __init__(self, document=None, error=None):
        self.document = document
        self.error = error

    def extract(self, file_path):
        if self.error is not None:
            raise self.error

        return self.document


@pytest.mark.parametrize(
    ("action", "expected_status"),
    [
        ("accept", "accept"),
        ("review", "review"),
        ("escalate", "escalate"),
    ],
)
def test_pipeline_status(action, expected_status):
    """Verify fidelity decisions for valid native PDF text."""

    extractor = FakeExtractor(make_document())

    with (
        patch(
            "backend.app.services.pipeline_service.calculate_fidelity",
            return_value={
                "action": action,
                "fidelity_score": 0.9,
                "risk": "low",
                "flagged": False,
                "issues": [],
            },
        ),
        patch(
            "backend.app.services.pipeline_service.determine_escalation",
            return_value={
                "decision": action,
                "retry_required": action != "accept",
                "strategy": "none",
                "target": "paragraph",
                "reason": [],
            },
        ),
    ):
        result = PipelineService(extractor).process("sample.pdf")

    assert result["status"] == expected_status
    assert result["block_count"] == 1
    assert result["unexecuted_route_count"] == 0

    block_result = result["block_results"][0]

    assert block_result["fidelity"]["action"] == action
    assert block_result["initial_extractor"] == "native_pdf"
    assert block_result["route"] == "native_pdf"
    assert block_result["requires_specialist"] is False
    assert block_result["route_executed"] is False


def test_pipeline_empty_document_requires_review():
    """An empty document must not be accepted."""

    document = make_document()
    document.pages[0].blocks = []

    result = PipelineService(
        FakeExtractor(document)
    ).process("sample.pdf")

    assert result["status"] == "review"
    assert result["block_count"] == 0
    assert result["unexecuted_route_count"] == 0


def test_native_text_avoids_unnecessary_ocr():
    """Usable native PDF text should not trigger OCR fallback."""

    result = PipelineService(
        FakeExtractor(make_document())
    ).process("sample.pdf")

    block = result["block_results"][0]

    assert block["initial_extractor"] == "native_pdf"
    assert block["route"] == "native_pdf"
    assert block["requires_specialist"] is False
    assert block["route_executed"] is False
    assert result["unexecuted_route_count"] == 0


def test_unexecuted_specialist_route_prevents_accept():
    """A fidelity ACCEPT must not hide an unexecuted OCR route."""

    document = make_document(text="")

    with patch(
        "backend.app.services.pipeline_service.calculate_fidelity",
        return_value={
            "action": "accept",
            "fidelity_score": 1.0,
            "risk": "low",
            "flagged": False,
            "issues": [],
        },
    ):
        result = PipelineService(
            FakeExtractor(document)
        ).process("sample.pdf")

    assert result["status"] == "review"
    assert result["unexecuted_route_count"] == 1
    assert result["block_results"][0]["route"] == "ocr"
    assert result["block_results"][0]["route_executed"] is False


def test_matching_route_allows_accept():
    """A matching native route can pass when fidelity accepts."""

    document = make_document()

    with (
        patch(
            "backend.app.services.pipeline_service.route_region"
        ) as mock_route,
        patch(
            "backend.app.services.pipeline_service.calculate_fidelity",
            return_value={
                "action": "accept",
                "fidelity_score": 1.0,
                "risk": "low",
                "flagged": False,
                "issues": [],
            },
        ),
    ):
        mock_route.return_value.route = "native_pdf"
        mock_route.return_value.reason_code = "native_text"
        mock_route.return_value.is_fallback = False

        result = PipelineService(
            FakeExtractor(document)
        ).process("sample.pdf")

    assert result["status"] == "accept"
    assert result["unexecuted_route_count"] == 0
    assert result["block_results"][0]["route"] == "native_pdf"


def test_unsupported_specialist_route_is_explicit():
    """An unavailable specialist route must be reported clearly."""

    document = make_document(text="")

    result = PipelineService(
        FakeExtractor(document)
    ).process("sample.pdf")

    block = result["block_results"][0]

    assert block["initial_extractor"] == "native_pdf"
    assert block["route"] == "ocr"
    assert block["route_executed"] is False
    assert block["route_status"] == "unsupported"
    assert block["requires_specialist"] is True

    assert result["status"] == "review"
    assert result["unexecuted_route_count"] == 1


def test_extractor_error_propagates():
    """Unexpected extractor failures must not be silently accepted."""

    extractor = FakeExtractor(
        error=RuntimeError("Extraction failed")
    )

    with pytest.raises(RuntimeError, match="Extraction failed"):
        PipelineService(extractor).process("sample.pdf")
