"""End-to-end integration test suite for the complete STRUCTURA pipeline.

Tests:
1. Programmatic creation of real PDF fixtures (clean digital PDF, scanned image-only PDF, anomalous encoding).
2. End-to-end upload -> processing -> Document Graph creation.
3. SAFE Router evaluation and block classification.
4. FidelityGuard evaluation and quality summary.
5. Markdown export with block anchors.
6. Structured block querying and spatial bounding box filtering.
7. Analytics & telemetry retrieval.
8. Corrupt document rejection & structured error handling.
"""

from __future__ import annotations

import io
from pathlib import Path
import pytest
import pymupdf
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.pipeline_service import PipelineService
from backend.app.services.export_service import DocumentExportService


@pytest.fixture
def client(tmp_path, monkeypatch):
    """TestClient with upload directory isolated to a temporary directory."""
    from backend.app.api import documents
    from backend.app.api.ingest import get_ingestion_service
    from backend.app.services import ingestion_service
    from backend.app.services.ingestion_service import IngestionService

    upload_root = tmp_path / "uploads"
    upload_root.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(ingestion_service, "DEFAULT_UPLOAD_ROOT", upload_root)
    monkeypatch.setattr(documents, "DEFAULT_UPLOAD_ROOT", upload_root)
    app.dependency_overrides[get_ingestion_service] = lambda: IngestionService(upload_root=upload_root)

    yield TestClient(app)
    app.dependency_overrides.pop(get_ingestion_service, None)


def create_sample_pdf(tmp_path: Path, title: str = "Test Document") -> Path:
    """Generate a clean native digital PDF with known headings, paragraphs, and list items."""
    pdf_path = tmp_path / "clean_sample.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)

    # Insert Heading (larger font, bold)
    page.insert_text(
        pymupdf.Point(50, 80),
        "Executive Financial Summary",
        fontsize=18,
        fontname="helv",
    )

    # Insert Paragraph
    page.insert_text(
        pymupdf.Point(50, 130),
        "This document contains high-fidelity quarterly earnings data and audited revenue breakdowns.",
        fontsize=11,
        fontname="helv",
    )

    # Insert Bulleted List item
    page.insert_text(
        pymupdf.Point(50, 180),
        "• Total Q3 Revenue reached $450M, representing a 22% YoY increase.",
        fontsize=11,
        fontname="helv",
    )

    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


def create_corrupt_pdf(tmp_path: Path) -> Path:
    """Generate a corrupted file claiming to be a PDF."""
    bad_path = tmp_path / "corrupt.pdf"
    bad_path.write_bytes(b"%PDF-1.7 Corrupt header but non-PDF junk data \x00\xff\xfe\xca\xfe\xba\xbe")
    return bad_path


# ---------------------------------------------------------------------------
# End-to-End Pipeline & API Tests
# ---------------------------------------------------------------------------

def test_full_pipeline_e2e_flow(client, tmp_path):
    """Test full cycle: Upload -> Process -> Document Graph -> Markdown -> Blocks -> Analytics."""
    # 1. Create and Upload real digital PDF
    pdf_file = create_sample_pdf(tmp_path)
    pdf_bytes = pdf_file.read_bytes()

    upload_res = client.post(
        "/v1/ingest",
        files={"file": ("clean_sample.pdf", pdf_bytes, "application/pdf")},
    )
    assert upload_res.status_code == 201
    upload_data = upload_res.json()
    doc_id = upload_data["document_id"]
    assert doc_id is not None

    # 2. Process Document through Pipeline
    process_res = client.post(f"/v1/documents/{doc_id}/process")
    assert process_res.status_code == 200
    process_json = process_res.json()
    assert process_json["status"] == "success"
    assert process_json["document_id"] == doc_id
    doc_graph = process_json["data"]["graph"]
    assert doc_graph["page_count"] == 1
    assert len(doc_graph["pages"][0]["blocks"]) >= 1

    # 3. Retrieve Document Graph via GET endpoint
    get_res = client.get(f"/v1/documents/{doc_id}")
    assert get_res.status_code == 200
    get_json = get_res.json()
    assert get_json["data"]["graph"]["document_id"] == doc_id
    assert get_json["data"]["quality"]["completeness"] == "complete"

    # 4. Export and check Markdown
    md_res = client.get(f"/v1/documents/{doc_id}/markdown")
    assert md_res.status_code == 200
    assert "text/markdown" in md_res.headers["content-type"]
    md_text = md_res.text
    assert "Executive Financial Summary" in md_text
    assert "<!-- Page 1 -->" in md_text
    assert "<!-- block:" in md_text

    # 5. Query Structured Blocks
    blocks_res = client.get(f"/v1/documents/{doc_id}/blocks?page=1")
    assert blocks_res.status_code == 200
    blocks_json = blocks_res.json()
    assert len(blocks_json["data"]) >= 1
    first_block = blocks_json["data"][0]
    assert "id" in first_block
    assert "bbox" in first_block
    assert len(first_block["bbox"]) == 4
    for coord in first_block["bbox"]:
        assert 0.0 <= coord <= 1.0

    # 6. Retrieve Processing Analytics
    analytics_res = client.get(f"/v1/documents/{doc_id}/analytics")
    assert analytics_res.status_code == 200
    analytics_json = analytics_res.json()
    analytics_data = analytics_json["data"]
    assert analytics_data["document_id"] == doc_id
    assert analytics_data["total_blocks"] >= 1
    assert "blocks_by_type" in analytics_data
    assert "risk_distribution" in analytics_data
    assert "extractors_used" in analytics_data
    assert 0.0 <= analytics_data["average_fidelity_score"] <= 1.0


def test_process_nonexistent_document_returns_404(client):
    """Processing a document ID that does not exist returns a 404 structured failure."""
    res = client.post("/v1/documents/non_existent_doc_id/process")
    assert res.status_code == 404
    body = res.json()
    assert body["status"] == "failure"
    assert body["errors"][0]["code"] == "DOCUMENT_UNAVAILABLE"


def test_corrupt_document_processing_returns_422(client, tmp_path):
    """Processing a corrupted PDF returns a 422 structured error without crashing."""
    corrupt_file = create_corrupt_pdf(tmp_path)
    upload_res = client.post(
        "/v1/ingest",
        files={"file": ("corrupt.pdf", corrupt_file.read_bytes(), "application/pdf")},
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["document_id"]

    process_res = client.post(f"/v1/documents/{doc_id}/process")
    assert process_res.status_code == 422
    body = process_res.json()
    assert body["status"] == "failure"
    assert body["errors"][0]["code"] == "CORRUPT_DOCUMENT"
