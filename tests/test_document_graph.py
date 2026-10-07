"""
tests/test_document_graph.py

Document Graph v1.0 — Pydantic model test suite.
All tests run from the repository root via: pytest
"""

import pytest
from pydantic import ValidationError

from backend.app.models.document_graph import (
    Block,
    BlockType,
    BoundingBox,
    Document,
    DocumentStatus,
    Metrics,
    Page,
    Risk,
    RiskLevel,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_valid_block(**overrides) -> dict:
    base = {
        "id": "block_001",
        "type": "paragraph",
        "page": 1,
        "bbox": [0.1, 0.2, 0.9, 0.8],
        "reading_order": 1,
    }
    base.update(overrides)
    return base


def make_valid_page(**overrides) -> dict:
    base = {
        "page": 1,
        "width": 612.0,
        "height": 792.0,
        "blocks": [],
    }
    base.update(overrides)
    return base


def make_valid_document(**overrides) -> dict:
    base = {
        "document_id": "doc_001",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# BoundingBox — standalone model tests
# ---------------------------------------------------------------------------

class TestBoundingBox:

    def test_valid_bbox(self):
        bb = BoundingBox(values=[0.1, 0.2, 0.9, 0.8])
        assert bb.values == [0.1, 0.2, 0.9, 0.8]

    def test_degenerate_bbox_allowed(self):
        """x0==x1 and y0==y1 must be accepted."""
        bb = BoundingBox(values=[0.5, 0.5, 0.5, 0.5])
        assert bb.values == [0.5, 0.5, 0.5, 0.5]

    def test_zero_origin_bbox(self):
        bb = BoundingBox(values=[0.0, 0.0, 1.0, 1.0])
        assert bb.values == [0.0, 0.0, 1.0, 1.0]

    def test_inverted_x_bbox_rejected(self):
        """x0 > x1 must be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            BoundingBox(values=[0.9, 0.1, 0.1, 0.8])
        assert "x0" in str(exc_info.value)

    def test_inverted_y_bbox_rejected(self):
        """y0 > y1 must be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            BoundingBox(values=[0.1, 0.9, 0.9, 0.1])
        assert "y0" in str(exc_info.value)

    def test_bbox_value_above_1_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            BoundingBox(values=[0.0, 0.0, 1.5, 0.5])
        error_text = str(exc_info.value)
        assert "out of range" in error_text or "x1" in error_text

    def test_bbox_negative_value_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            BoundingBox(values=[-0.1, 0.0, 0.9, 0.8])
        error_text = str(exc_info.value)
        assert "out of range" in error_text or "x0" in error_text

    def test_bbox_wrong_length_too_short_rejected(self):
        with pytest.raises(ValidationError):
            BoundingBox(values=[0.1, 0.2, 0.9])

    def test_bbox_wrong_length_too_long_rejected(self):
        with pytest.raises(ValidationError):
            BoundingBox(values=[0.1, 0.2, 0.9, 0.8, 0.5])

    def test_bbox_error_message_inverted_x(self):
        """Error message must mention x0 and x1."""
        with pytest.raises(ValidationError) as exc_info:
            BoundingBox(values=[0.8, 0.1, 0.2, 0.9])
        msg = str(exc_info.value)
        assert "x0" in msg and "x1" in msg

    def test_bbox_error_message_inverted_y(self):
        """Error message must mention y0 and y1."""
        with pytest.raises(ValidationError) as exc_info:
            BoundingBox(values=[0.1, 0.9, 0.9, 0.2])
        msg = str(exc_info.value)
        assert "y0" in msg and "y1" in msg

    def test_from_list_helper(self):
        bb = BoundingBox.from_list([0.0, 0.0, 0.5, 0.5])
        assert bb.as_list() == [0.0, 0.0, 0.5, 0.5]


# ---------------------------------------------------------------------------
# Block — bbox validation via Block model
# ---------------------------------------------------------------------------

class TestBlockBbox:

    def test_valid_block(self):
        b = Block(**make_valid_block())
        assert b.id == "block_001"

    def test_block_degenerate_bbox_allowed(self):
        """[0.5, 0.5, 0.5, 0.5] must be accepted inside a Block."""
        b = Block(**make_valid_block(bbox=[0.5, 0.5, 0.5, 0.5]))
        assert b.bbox == [0.5, 0.5, 0.5, 0.5]

    def test_block_inverted_x_bbox_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            Block(**make_valid_block(bbox=[0.9, 0.1, 0.1, 0.8]))
        assert "x0" in str(exc_info.value)

    def test_block_inverted_y_bbox_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            Block(**make_valid_block(bbox=[0.1, 0.9, 0.9, 0.1]))
        assert "y0" in str(exc_info.value)

    def test_block_bbox_out_of_range_rejected(self):
        with pytest.raises(ValidationError):
            Block(**make_valid_block(bbox=[0.0, 0.0, 1.1, 0.5]))

    def test_block_empty_id_rejected(self):
        """An empty block ID must be rejected."""
        with pytest.raises(ValidationError):
            Block(**make_valid_block(id=""))

    def test_block_page_zero_rejected(self):
        """page=0 must be rejected (pages are 1-indexed)."""
        with pytest.raises(ValidationError):
            Block(**make_valid_block(page=0))

    def test_block_page_negative_rejected(self):
        with pytest.raises(ValidationError):
            Block(**make_valid_block(page=-1))

    def test_block_extra_field_rejected(self):
        with pytest.raises(ValidationError):
            Block(**make_valid_block(nonexistent_field="oops"))


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

class TestPage:

    def test_valid_page(self):
        p = Page(**make_valid_page())
        assert p.page == 1

    def test_page_zero_rejected(self):
        """page=0 must be rejected."""
        with pytest.raises(ValidationError):
            Page(**make_valid_page(page=0))

    def test_page_negative_rejected(self):
        with pytest.raises(ValidationError):
            Page(**make_valid_page(page=-5))

    def test_width_zero_rejected(self):
        """width=0 must be rejected (must be > 0)."""
        with pytest.raises(ValidationError):
            Page(**make_valid_page(width=0))

    def test_width_negative_rejected(self):
        with pytest.raises(ValidationError):
            Page(**make_valid_page(width=-1.0))

    def test_height_negative_rejected(self):
        """height < 0 must be rejected."""
        with pytest.raises(ValidationError):
            Page(**make_valid_page(height=-10.0))

    def test_height_zero_rejected(self):
        with pytest.raises(ValidationError):
            Page(**make_valid_page(height=0))

    def test_page_extra_field_rejected(self):
        """Extra fields on Page must be rejected."""
        with pytest.raises(ValidationError):
            Page(**make_valid_page(surprise="field"))


# ---------------------------------------------------------------------------
# Risk
# ---------------------------------------------------------------------------

class TestRisk:

    def test_valid_risk(self):
        r = Risk(score=0.12, level="low", signals=["numeric_consistency_pass"])
        assert r.score == 0.12
        assert r.level == RiskLevel.low

    def test_risk_score_above_1_rejected(self):
        with pytest.raises(ValidationError):
            Risk(score=1.5, level="low")

    def test_risk_score_negative_rejected(self):
        with pytest.raises(ValidationError):
            Risk(score=-0.1, level="medium")

    def test_risk_extra_field_rejected(self):
        """Extra fields on Risk must be rejected."""
        with pytest.raises(ValidationError):
            Risk(score=0.5, level="low", unknown_field="bad")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

class TestMetrics:

    def test_valid_metrics_all_none(self):
        m = Metrics()
        assert m.processing_time_seconds is None

    def test_valid_metrics_with_values(self):
        m = Metrics(processing_time_seconds=1.5, pages_per_second=10.0)
        assert m.processing_time_seconds == 1.5

    def test_negative_processing_time_rejected(self):
        """Negative processing_time_seconds must be rejected."""
        with pytest.raises(ValidationError):
            Metrics(processing_time_seconds=-1.0)

    def test_negative_pages_per_second_rejected(self):
        with pytest.raises(ValidationError):
            Metrics(pages_per_second=-5.0)

    def test_provenance_coverage_above_1_rejected(self):
        with pytest.raises(ValidationError):
            Metrics(provenance_coverage=1.5)

    def test_escalated_regions_above_100_rejected(self):
        with pytest.raises(ValidationError):
            Metrics(escalated_regions_percent=101.0)

    def test_negative_cost_rejected(self):
        """Negative cost metrics must be rejected."""
        with pytest.raises(ValidationError):
            Metrics(estimated_cost_per_1000_pages=-0.01)

    def test_negative_cost_per_correct_page_rejected(self):
        with pytest.raises(ValidationError):
            Metrics(cost_per_correct_page=-1.0)

    def test_metrics_extra_field_rejected(self):
        """Extra fields on Metrics must be rejected."""
        with pytest.raises(ValidationError):
            Metrics(unknown_metric=42.0)


# ---------------------------------------------------------------------------
# Document
# ---------------------------------------------------------------------------

class TestDocument:

    def test_valid_minimal_document(self):
        d = Document(**make_valid_document())
        assert d.document_id == "doc_001"
        assert d.status == DocumentStatus.pending
        assert d.pages == []

    def test_valid_document_with_page(self):
        page_data = make_valid_page()
        d = Document(**make_valid_document(pages=[page_data], page_count=1))
        assert len(d.pages) == 1

    def test_empty_document_id_rejected(self):
        """Empty document_id must be rejected."""
        with pytest.raises(ValidationError):
            Document(document_id="")

    def test_document_extra_field_rejected(self):
        """Extra fields on Document must be rejected."""
        with pytest.raises(ValidationError):
            Document(**make_valid_document(rogue_field="bad"))

    def test_document_status_enum_valid(self):
        d = Document(**make_valid_document(status="completed"))
        assert d.status == DocumentStatus.completed

    def test_document_status_invalid_rejected(self):
        with pytest.raises(ValidationError):
            Document(**make_valid_document(status="unknown_status"))

    def test_document_negative_page_count_rejected(self):
        with pytest.raises(ValidationError):
            Document(**make_valid_document(page_count=-1))


# ---------------------------------------------------------------------------
# Integration — full Document Graph round-trip (mirrors mock_output.json)
# ---------------------------------------------------------------------------

class TestIntegration:

    def test_full_document_graph_roundtrip(self):
        block_data = {
            "id": "block_042",
            "type": "table",
            "page": 31,
            "bbox": [0.13, 0.31, 0.87, 0.69],
            "reading_order": 8,
            "content": {
                "headers": ["Debt Instrument", "Amount"],
                "rows": [
                    ["Term Loan A", "$100M"],
                    ["Term Loan B", "$200M"],
                    ["Notes", "$125M"],
                    ["Total Debt", "$425M"],
                ],
            },
            "extractor": "table_engine",
            "risk": {
                "score": 0.12,
                "level": "low",
                "signals": ["numeric_consistency_pass"],
            },
            "flags": [],
            "traceable": True,
        }
        page_data = {
            "page": 31,
            "width": 612.0,
            "height": 792.0,
            "blocks": [block_data],
        }
        doc_data = {
            "document_id": "doc_001",
            "filename": "acquisition_report.pdf",
            "format": "pdf",
            "status": "completed",
            "page_count": 31,
            "pages": [page_data],
            "metrics": {
                "processing_time_seconds": None,
                "pages_per_second": None,
                "provenance_coverage": None,
                "escalated_regions_percent": None,
                "estimated_cost_per_1000_pages": None,
                "cost_per_correct_page": None,
            },
        }
        doc = Document(**doc_data)
        assert doc.document_id == "doc_001"
        assert doc.status == DocumentStatus.completed
        assert len(doc.pages) == 1
        assert len(doc.pages[0].blocks) == 1
        block = doc.pages[0].blocks[0]
        assert block.id == "block_042"
        assert block.type == BlockType.table
        assert block.risk.level == RiskLevel.low
        # Verify JSON round-trip preserves data
        reloaded = Document.model_validate(doc.model_dump())
        assert reloaded.document_id == doc.document_id
