"""Checkpoint 9: file ingestion tests. All writes go to pytest tmp_path."""

import asyncio
import io
import uuid

import pytest
from fastapi.testclient import TestClient
from pydantic import TypeAdapter, ValidationError

from backend.app.api.ingest import get_ingestion_service
from backend.app.main import app
from backend.app.models.api_responses import ApiResponse, FailureResponse, SuccessResponse
from backend.app.models.ingestion import IngestedDocument
from backend.app.services import ingestion_service as svc
from backend.app.services.ingestion_service import (
    SUPPORTED_FORMATS,
    FileTooLargeError,
    IngestionService,
    UnsupportedFormatError,
)

MAX_BYTES = 50 * 1024 * 1024
ResponseAdapter = TypeAdapter(ApiResponse[IngestedDocument])

PDF = "application/pdf"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


# ----------------------------------------------------------------- fixtures
@pytest.fixture
def upload_root(tmp_path):
    return tmp_path / "uploads"


@pytest.fixture
def use_service(upload_root):
    def _use(**kwargs):
        root = kwargs.pop("root", upload_root)
        app.dependency_overrides[get_ingestion_service] = lambda: IngestionService(
            upload_root=root, **kwargs
        )

    yield _use
    app.dependency_overrides.pop(get_ingestion_service, None)


@pytest.fixture
def client(use_service):
    use_service()
    return TestClient(app)


def upload(client, filename, content=b"data", content_type=PDF):
    return client.post("/v1/ingest", files={"file": (filename, content, content_type)})


def stored(root):
    return sorted(p.name for p in root.iterdir()) if root.exists() else []


def assert_success(response):
    assert response.status_code == 201
    parsed = ResponseAdapter.validate_python(response.json())
    assert isinstance(parsed, SuccessResponse)
    return parsed


def assert_failure(response, status, code, category="request"):
    assert response.status_code == status
    parsed = ResponseAdapter.validate_python(response.json())
    assert isinstance(parsed, FailureResponse)
    assert len(parsed.errors) >= 1
    assert parsed.request_id
    assert parsed.data is None
    error = parsed.errors[0]
    assert error.code == code
    assert error.category == category
    return parsed


# -------------------------------------------------------------- happy paths
@pytest.mark.parametrize(
    "filename,fmt,content_type",
    [
        ("report.pdf", "pdf", PDF),
        ("sheet.xlsx", "xlsx", XLSX),
        ("deck.pptx", "pptx", PPTX),
        ("image.png", "png", "image/png"),
        ("photo.jpg", "jpg", "image/jpeg"),
        ("photo.jpeg", "jpeg", "image/jpeg"),
        ("scan.tiff", "tiff", "image/tiff"),
    ],
)
def test_supported_formats_are_ingested(client, upload_root, filename, fmt, content_type):
    content = b"hello-" + fmt.encode()
    response = upload(client, filename, content, content_type)
    parsed = assert_success(response)

    data = parsed.data
    assert uuid.UUID(data.document_id).version == 4
    assert data.format == fmt
    assert data.filename == filename
    assert data.content_type == content_type
    assert data.size_bytes == len(content)
    assert data.status == "pending"
    assert data.storage_key == f"uploads/{data.document_id}.{fmt}"
    assert (upload_root / f"{data.document_id}.{fmt}").read_bytes() == content
    assert stored(upload_root) == [f"{data.document_id}.{fmt}"]

    # Envelope contract
    assert parsed.response_version == "1.0"
    assert parsed.request_id
    assert parsed.document_id == data.document_id
    assert parsed.errors == []
    assert parsed.meta == {}
    assert SuccessResponse[IngestedDocument].model_validate(response.json())


def test_uppercase_extension(client, upload_root):
    data = assert_success(upload(client, "REPORT.PDF", b"x")).data
    assert data.format == "pdf"
    assert data.filename == "REPORT.PDF"
    assert stored(upload_root) == [f"{data.document_id}.pdf"]


def test_each_upload_gets_a_unique_document_id(client, upload_root):
    first = assert_success(upload(client, "a.pdf")).data.document_id
    second = assert_success(upload(client, "a.pdf")).data.document_id
    assert first != second
    assert len(stored(upload_root)) == 2


def test_octet_stream_content_type_accepted_for_supported_extension(client):
    data = assert_success(upload(client, "report.pdf", b"x", "application/octet-stream")).data
    assert data.content_type == PDF  # canonical type for the validated extension


def test_mismatched_specific_content_type_rejected(client, upload_root):
    response = upload(client, "report.pdf", b"x", "image/png")
    assert_failure(response, 400, "UNSUPPORTED_FORMAT")
    assert stored(upload_root) == []


# --------------------------------------------------------------- validation
def test_empty_file_rejected(client, upload_root):
    parsed = assert_failure(upload(client, "empty.pdf", b""), 400, "INVALID_FILE")
    error = parsed.errors[0]
    assert error.recoverable is False
    assert error.recovery is None
    assert error.location.scope == "request"
    assert error.location.field_path == ["body", "file"]
    assert stored(upload_root) == []


@pytest.mark.parametrize(
    "filename", ["malware.exe", "notes.txt", "doc.docx", "scan.tif", "noextension", "x.pdf.exe", "file.pdf."]
)
def test_unsupported_extension_rejected(client, upload_root, filename):
    parsed = assert_failure(upload(client, filename, b"x", "application/octet-stream"), 400, "UNSUPPORTED_FORMAT")
    assert parsed.errors[0].details["supported_formats"] == sorted(SUPPORTED_FORMATS)
    assert stored(upload_root) == []


def test_missing_file_rejected(client):
    parsed = assert_failure(client.post("/v1/ingest"), 400, "REQUEST_VALIDATION_FAILED")
    assert parsed.errors[0].location.field_path == ["body", "file"]


def test_wrong_field_name_counts_as_missing_file(client):
    response = client.post("/v1/ingest", files={"upload": ("a.pdf", b"x", PDF)})
    assert_failure(response, 400, "REQUEST_VALIDATION_FAILED")


def test_file_exactly_at_limit_accepted(client, upload_root):
    data = assert_success(upload(client, "big.pdf", b"\0" * MAX_BYTES)).data
    assert data.size_bytes == MAX_BYTES
    assert (upload_root / f"{data.document_id}.pdf").stat().st_size == MAX_BYTES


def test_file_above_limit_rejected_and_leaves_no_partial_file(client, upload_root):
    response = upload(client, "big.pdf", b"\0" * (MAX_BYTES + 1))
    parsed = assert_failure(response, 413, "DOCUMENT_TOO_LARGE")
    assert parsed.errors[0].details == {"max_bytes": MAX_BYTES}
    assert stored(upload_root) == []


def test_small_limit_with_chunking(use_service, client, upload_root):
    use_service(max_bytes=10, chunk_size=3)
    assert_success(upload(client, "ok.pdf", b"0123456789"))
    before = stored(upload_root)
    assert_failure(upload(client, "no.pdf", b"0123456789A"), 413, "DOCUMENT_TOO_LARGE")
    assert stored(upload_root) == before  # nothing new, no .part leftovers


# ------------------------------------------------- paths and filename safety
@pytest.mark.parametrize(
    "filename,expected",
    [
        ("../../etc/passwd.pdf", "passwd.pdf"),
        ("..\\..\\evil.pdf", "evil.pdf"),
        ("/etc/passwd.pdf", "passwd.pdf"),
        ("C:\\Windows\\system.pdf", "system.pdf"),
    ],
)
def test_path_components_in_filename_cannot_affect_storage(client, tmp_path, upload_root, filename, expected):
    response = upload(client, filename, b"x")
    data = assert_success(response).data
    assert data.filename == expected
    assert "/" not in data.filename and "\\" not in data.filename
    assert data.storage_key == f"uploads/{data.document_id}.pdf"
    assert stored(upload_root) == [f"{data.document_id}.pdf"]
    assert sorted(p.name for p in tmp_path.iterdir()) == ["uploads"]  # nothing escaped the root


@pytest.mark.parametrize(
    "filename",
    ["résumé final #1 [v2] 100%.pdf", "a b;c=d&e.pdf", "weird'name~`!@$^().pdf", "  spaced name .pdf"],
)
def test_odd_filename_characters_do_not_affect_storage_name(client, upload_root, filename):
    data = assert_success(upload(client, filename, b"x")).data
    assert stored(upload_root) == [f"{data.document_id}.pdf"]
    assert data.storage_key == f"uploads/{data.document_id}.pdf"


def test_absolute_paths_never_appear_in_any_response(client, tmp_path, use_service):
    success = upload(client, "a.pdf", b"x")
    empty = upload(client, "a.pdf", b"")
    bad = upload(client, "a.exe", b"x")
    for response in (success, empty, bad):
        assert str(tmp_path) not in response.text
        assert str(tmp_path).replace("\\", "/") not in response.text
    key = success.json()["data"]["storage_key"]
    assert not key.startswith("/") and ":" not in key and "\\" not in key


# ----------------------------------------------------------- failure cleanup
def test_storage_failure_returns_internal_error_without_leaks(
    client, use_service, tmp_path, upload_root, monkeypatch
):
    use_service(chunk_size=4)
    calls = {"n": 0}
    original = IngestionService._write_chunk

    def flaky(self, handle, chunk):
        calls["n"] += 1
        if calls["n"] == 2:
            raise OSError(f"disk exploded at {tmp_path}")
        original(self, handle, chunk)

    monkeypatch.setattr(IngestionService, "_write_chunk", flaky)
    response = upload(client, "a.pdf", b"0123456789")

    parsed = assert_failure(response, 500, "INTERNAL_ERROR", category="internal")
    error = parsed.errors[0]
    assert error.recoverable is True
    assert error.recovery.action == "retry"
    assert "exploded" not in response.text
    assert str(tmp_path) not in response.text
    assert stored(upload_root) == []  # partial file removed


def test_unexpected_exception_is_contained(client, use_service, upload_root, monkeypatch):
    def boom(self, handle, chunk):
        raise RuntimeError("secret internals")

    monkeypatch.setattr(IngestionService, "_write_chunk", boom)
    response = upload(client, "a.pdf", b"x")
    assert_failure(response, 500, "INTERNAL_ERROR", category="internal")
    assert "secret internals" not in response.text
    assert "Traceback" not in response.text
    assert stored(upload_root) == []


def test_unwritable_upload_root_returns_internal_error(client, use_service, tmp_path):
    blocker = tmp_path / "blocker"
    blocker.write_text("i am a file, not a directory")
    use_service(root=blocker / "uploads")
    response = upload(client, "a.pdf", b"x")
    assert_failure(response, 500, "INTERNAL_ERROR", category="internal")
    assert str(tmp_path) not in response.text


# ---------------------------------------------------------- response contract
def test_error_ids_are_unique_across_failures(client):
    ids = {upload(client, "a.exe", b"x").json()["errors"][0]["error_id"] for _ in range(3)}
    assert len(ids) == 3


def test_request_ids_are_populated_and_unique(client):
    ids = {upload(client, "a.pdf", b"x").json()["request_id"] for _ in range(3)}
    assert len(ids) == 3 and all(ids)


def test_failure_envelope_has_all_keys_and_null_document_id(client):
    body = upload(client, "a.exe", b"x").json()
    assert set(body) == {
        "response_version", "status", "request_id", "message",
        "job_id", "document_id", "data", "errors", "meta",
    }
    assert body["status"] == "failure"
    assert body["data"] is None and body["document_id"] is None


def test_health_endpoint_still_works(client):
    assert client.get("/v1/health").status_code == 200


# ------------------------------------------------------------ service units
class BytesReader:
    def __init__(self, data: bytes):
        self._buf = io.BytesIO(data)
        self.sizes = []

    async def read(self, size: int = -1) -> bytes:
        self.sizes.append(size)
        return self._buf.read(size)


def run(coro):
    return asyncio.run(coro)


def test_supported_format_registry_is_centralized():
    assert set(SUPPORTED_FORMATS) == {"pdf", "xlsx", "pptx", "png", "jpg", "jpeg", "tiff"}
    for ext, spec in SUPPORTED_FORMATS.items():
        assert spec.format == ext
        assert spec.content_types


@pytest.mark.parametrize(
    "filename,expected",
    [
        ("REPORT.PDF", "pdf"), ("Sheet.XLSX", "xlsx"), ("a.b.c.PnG", "png"),
        ("noext", ""), (".pdf", ""), ("x.pdf.", ""), ("dir/../x.JPEG", "jpeg"),
    ],
)
def test_extract_extension(filename, expected):
    assert svc.extract_extension(filename) == expected


@pytest.mark.parametrize("raw", [None, "", "application/octet-stream", "APPLICATION/PDF", "application/pdf; charset=binary"])
def test_resolve_content_type_accepts_generic_and_matching(raw):
    assert svc.resolve_content_type(SUPPORTED_FORMATS["pdf"], raw) == PDF


def test_resolve_content_type_rejects_contradiction():
    with pytest.raises(UnsupportedFormatError):
        svc.resolve_content_type(SUPPORTED_FORMATS["pdf"], "image/png")


def test_service_reads_in_bounded_chunks(upload_root):
    reader = BytesReader(b"0123456789")
    service = IngestionService(upload_root=upload_root, chunk_size=4)
    result = run(service.ingest(filename="a.pdf", content_type=None, reader=reader))
    assert result.size_bytes == 10
    assert reader.sizes and all(s == 4 for s in reader.sizes)  # never read(-1)


def test_service_counts_bytes_itself_and_cleans_up(upload_root):
    service = IngestionService(upload_root=upload_root, max_bytes=10, chunk_size=4)
    with pytest.raises(FileTooLargeError):
        run(service.ingest(filename="a.pdf", content_type=None, reader=BytesReader(b"x" * 11)))
    assert stored(upload_root) == []


def test_service_does_not_create_final_file_until_complete(upload_root):
    service = IngestionService(upload_root=upload_root, chunk_size=4)
    result = run(service.ingest(filename="a.png", content_type="image/png", reader=BytesReader(b"abcdefgh")))
    assert stored(upload_root) == [f"{result.document_id}.png"]


# ------------------------------------------------------------- model checks
def valid_doc(**overrides):
    data = {
        "document_id": "d1", "filename": "a.pdf", "format": "pdf", "content_type": PDF,
        "size_bytes": 1, "status": "pending", "storage_key": "uploads/d1.pdf",
    }
    data.update(overrides)
    return data


def test_ingested_document_valid():
    assert IngestedDocument.model_validate(valid_doc()).status == "pending"


@pytest.mark.parametrize(
    "overrides",
    [
        {"storage_key": "/abs/d1.pdf"}, {"storage_key": "C:\\x\\d1.pdf"},
        {"storage_key": "../d1.pdf"}, {"storage_key": "uploads\\d1.pdf"},
        {"size_bytes": 0}, {"size_bytes": -1}, {"status": "ready"}, {"format": "gif"},
        {"document_id": ""}, {"filename": ""}, {"content_type": ""}, {"extra": 1},
    ],
)
def test_ingested_document_invalid(overrides):
    with pytest.raises(ValidationError):
        IngestedDocument.model_validate(valid_doc(**overrides))
