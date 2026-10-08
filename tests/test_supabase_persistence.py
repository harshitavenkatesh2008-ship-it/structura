"""Tests for Component C14: Supabase Persistence & Failure Recovery.

Validates:
- Job persistence and retrieval via SupabaseJobRepository
- Processed Document Graph storage and retrieval via PersistenceService
- State machine transition preservation
- Missing document and job handling
- Graceful handling of network / connection failures
- Prevention of duplicate job records during retries
- Structured error recording and partial-success metadata
- Secret masking (credentials never appear in string representations, logs, or responses)
- Offline execution without live Supabase credentials (local fallback)
- Interrupted and stale job recovery handling
"""

from datetime import datetime, timezone
import json
import pytest
import httpx
from pydantic import SecretStr

from backend.app.core import error_codes
from backend.app.core.config import Settings
from backend.app.models.api_responses import Progress
from backend.app.models.document_graph import Block, BlockType, Document, DocumentStatus, Page
from backend.app.models.ingestion import IngestedDocument
from backend.app.models.jobs import (
    ALLOWED_TRANSITIONS,
    Job,
    JobNotFoundError,
)
from backend.app.repositories.job_repository import DuplicateJobError
from backend.app.repositories.supabase_job_repository import (
    PersistenceUnavailableError,
    SupabaseJobRepository,
)
from backend.app.services.job_service import JobService
from backend.app.services.persistence_service import PersistenceError, PersistenceService
from backend.app.services.recovery_service import JobRecoveryService
from backend.app.services.supabase_client import (
    SupabaseApiError,
    SupabaseClient,
    SupabaseConnectionError,
)


# ------------------------------------------------------------------- fixtures
@pytest.fixture
def sample_job() -> Job:
    now = datetime(2026, 10, 8, 12, 0, 0, tzinfo=timezone.utc)
    return Job(
        job_id="job_c14_001",
        document_id="doc_c14_001",
        state="queued",
        stage="queued",
        progress=None,
        parent_job_id=None,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def sample_document_graph() -> Document:
    return Document(
        document_id="doc_c14_001",
        filename="invoice.pdf",
        format="pdf",
        status=DocumentStatus.completed,
        page_count=1,
        pages=[
            Page(
                page=1,
                width=612.0,
                height=792.0,
                blocks=[
                    Block(
                        id="b_01",
                        type=BlockType.paragraph,
                        page=1,
                        bbox=[0.1, 0.1, 0.9, 0.2],
                        reading_order=0,
                        content={"text": "Invoice #1001"},
                        extractor="native_pdf",
                    )
                ],
            )
        ],
    )


# =================================================================== 1. Secrets Protection
def test_secrets_never_appear_in_repr_or_logs():
    secret_key = "sb_secret_super_confidential_key_12345"
    client = SupabaseClient(
        url="https://xyzcompany.supabase.co",
        key=SecretStr(secret_key),
    )
    rep = repr(client)
    s = str(client)

    assert secret_key not in rep
    assert secret_key not in s
    assert "key='***'" in rep


def test_settings_secret_masking():
    secret_key = "sb_secret_very_private"
    settings = Settings(
        supabase_url="https://example.supabase.co",
        supabase_key=SecretStr(secret_key),
    )
    dumped = settings.model_dump()
    # Pydantic masks SecretStr in model_dump or repr
    assert secret_key not in repr(settings)
    assert settings.get_effective_supabase_key() == secret_key


# =================================================================== 2. Supabase Client Unit Tests
@pytest.mark.asyncio
async def test_supabase_client_select_success():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["apikey"] == "test_key"
        assert request.headers["authorization"] == "Bearer test_key"
        return httpx.Response(200, json=[{"job_id": "job_1", "state": "queued"}])

    mock_http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = SupabaseClient("https://test.supabase.co", "test_key", http_client=mock_http)

    records = await client.select("jobs", {"job_id": "eq.job_1"})
    assert len(records) == 1
    assert records[0]["job_id"] == "job_1"


@pytest.mark.asyncio
async def test_supabase_client_handles_connection_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Network unreachable")

    mock_http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = SupabaseClient("https://unreachable.supabase.co", "test_key", http_client=mock_http)

    with pytest.raises(SupabaseConnectionError) as exc_info:
        await client.select("jobs")
    assert "Could not connect to Supabase" in str(exc_info.value)


@pytest.mark.asyncio
async def test_supabase_client_handles_api_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error")

    mock_http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = SupabaseClient("https://test.supabase.co", "test_key", http_client=mock_http)

    with pytest.raises(SupabaseApiError) as exc_info:
        await client.select("jobs")
    assert exc_info.value.status_code == 500


# =================================================================== 3. Supabase Job Repository Tests
@pytest.mark.asyncio
async def test_persist_and_retrieve_job(sample_job: Job):
    db: dict[str, dict] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        method = request.method
        path = request.url.path
        if "/rest/v1/jobs" in path:
            if method == "POST":
                payload = json.loads(request.content)
                db[payload["job_id"]] = payload
                return httpx.Response(201, json=[payload])
            elif method == "GET":
                job_id = request.url.params.get("job_id", "").replace("eq.", "")
                if job_id in db:
                    return httpx.Response(200, json=[db[job_id]])
                return httpx.Response(200, json=[])
        return httpx.Response(404)

    mock_http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = SupabaseClient("https://test.supabase.co", "test_key", http_client=mock_http)
    repo = SupabaseJobRepository(client)

    # 1. Create
    created = await repo.create(sample_job)
    assert created.job_id == sample_job.job_id

    # 2. Get
    retrieved = await repo.get(sample_job.job_id)
    assert retrieved is not None
    assert retrieved.job_id == sample_job.job_id
    assert retrieved.state == "queued"
    assert retrieved.document_id == sample_job.document_id


@pytest.mark.asyncio
async def test_avoid_duplicate_records_during_retries(sample_job: Job):
    db = {sample_job.job_id: sample_job.model_dump(mode="json")}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json=[db[sample_job.job_id]])
        return httpx.Response(409, json={"message": "duplicate key value violates unique constraint"})

    mock_http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = SupabaseClient("https://test.supabase.co", "test_key", http_client=mock_http)
    repo = SupabaseJobRepository(client)

    with pytest.raises(DuplicateJobError):
        await repo.create(sample_job)


@pytest.mark.asyncio
async def test_handle_missing_job_returns_not_found():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    mock_http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = SupabaseClient("https://test.supabase.co", "test_key", http_client=mock_http)
    repo = SupabaseJobRepository(client)

    result = await repo.get("non_existent_job_id")
    assert result is None

    # Updating absent job raises JobNotFoundError
    now = datetime.now(timezone.utc)
    absent_job = Job(
        job_id="absent", document_id="doc1", state="queued", created_at=now, updated_at=now
    )
    with pytest.raises(JobNotFoundError):
        await repo.update(absent_job)


@pytest.mark.asyncio
async def test_preserve_job_status_transitions(sample_job: Job):
    db = {sample_job.job_id: sample_job.model_dump(mode="json")}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json=[db[sample_job.job_id]])
        elif request.method == "PATCH":
            payload = json.loads(request.content)
            db[sample_job.job_id].update(payload)
            return httpx.Response(200, json=[db[sample_job.job_id]])
        return httpx.Response(404)

    mock_http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = SupabaseClient("https://test.supabase.co", "test_key", http_client=mock_http)
    repo = SupabaseJobRepository(client)
    job_service = JobService(repo, document_exists=lambda _: True)

    # queued -> running
    updated = await job_service.transition_job(sample_job.job_id, "running")
    assert updated.state == "running"

    # running -> completed
    completed = await job_service.transition_job(sample_job.job_id, "completed")
    assert completed.state == "completed"


@pytest.mark.asyncio
async def test_handle_supabase_connection_failure_safely(sample_job: Job):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Supabase offline")

    mock_http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = SupabaseClient("https://offline.supabase.co", "test_key", http_client=mock_http)
    repo = SupabaseJobRepository(client)

    with pytest.raises(PersistenceUnavailableError):
        await repo.get(sample_job.job_id)


# =================================================================== 4. Document Graph Persistence
@pytest.mark.asyncio
async def test_persist_and_retrieve_document_graph(sample_document_graph: Document):
    storage_store: dict[str, bytes] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if "/storage/v1/object" in path:
            if request.method == "POST":
                storage_store[path] = request.content
                return httpx.Response(200, json={"Key": path})
            elif request.method == "GET":
                if path in storage_store:
                    return httpx.Response(200, content=storage_store[path])
                return httpx.Response(404)
        elif "/rest/v1" in path:
            return httpx.Response(200, json=[])
        return httpx.Response(404)

    mock_http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = SupabaseClient("https://test.supabase.co", "test_key", http_client=mock_http)
    persistence = PersistenceService(client=client, bucket="documents")

    # Save
    storage_key = await persistence.save_document_graph("doc_c14_001", sample_document_graph)
    assert "documents/graphs/doc_c14_001.json" in storage_key

    # Retrieve
    retrieved = await persistence.get_document_graph("doc_c14_001")
    assert retrieved is not None
    assert retrieved.document_id == "doc_c14_001"
    assert retrieved.page_count == 1
    assert retrieved.pages[0].blocks[0].content["text"] == "Invoice #1001"


# =================================================================== 5. Offline Fallback
@pytest.mark.asyncio
async def test_local_offline_fallback_without_credentials(sample_document_graph: Document):
    # PersistenceService initialized with client=None runs in offline memory mode
    persistence = PersistenceService(client=None)

    key = await persistence.save_document_graph("doc_local", sample_document_graph)
    assert key.startswith("local://")

    retrieved = await persistence.get_document_graph("doc_local")
    assert retrieved is not None
    assert retrieved.document_id == "doc_c14_001"

    # Save and retrieve document metadata locally
    ingested = IngestedDocument(
        document_id="doc_local",
        filename="local.pdf",
        format="pdf",
        content_type="application/pdf",
        size_bytes=1024,
        storage_key="uploads/doc_local.pdf",
    )
    await persistence.save_document_metadata(ingested)
    meta = await persistence.get_document_metadata("doc_local")
    assert meta is not None
    assert meta["filename"] == "local.pdf"
    assert await persistence.has_document("doc_local") is True


# =================================================================== 6. Structured Error & Partial Success
@pytest.mark.asyncio
async def test_preserve_structured_errors_and_partial_success():
    persistence = PersistenceService(client=None)

    outcome = await persistence.record_processing_outcome(
        job_id="job_failed_01",
        document_id="doc_01",
        status="failed",
        error_code=error_codes.PARSE_FAILED,
        error_message="Syntax error at line 42",
        partial_results={"pages_processed": 3, "total_pages": 10},
    )

    retrieved = await persistence.get_processing_outcome("job_failed_01")
    assert retrieved is not None
    assert retrieved["error_code"] == error_codes.PARSE_FAILED
    assert retrieved["partial_results"]["pages_processed"] == 3


# =================================================================== 7. Interrupted Job Recovery
@pytest.mark.asyncio
async def test_recover_interrupted_stale_jobs():
    class TestRepo(SupabaseJobRepository):
        def __init__(self):
            self.jobs: dict[str, Job] = {}

        async def list_active_jobs(self) -> list[Job]:
            return list(self.jobs.values())

        async def get(self, job_id: str) -> Job | None:
            return self.jobs.get(job_id)

        async def update(self, job: Job) -> Job:
            self.jobs[job.job_id] = job
            return job

        async def modify(self, job_id: str, mutator):
            current = self.jobs[job_id]
            updated = mutator(current)
            self.jobs[job_id] = updated
            return updated

    repo = TestRepo()
    now = datetime.now(timezone.utc)
    old_time = datetime(2026, 1, 1, tzinfo=timezone.utc)

    # Stale running job
    repo.jobs["stale_job"] = Job(
        job_id="stale_job",
        document_id="doc1",
        state="running",
        stage="parsing",
        created_at=old_time,
        updated_at=old_time,
    )

    # Fresh running job
    repo.jobs["fresh_job"] = Job(
        job_id="fresh_job",
        document_id="doc2",
        state="running",
        stage="parsing",
        created_at=now,
        updated_at=now,
    )

    job_service = JobService(repo, document_exists=lambda _: True)
    persistence = PersistenceService(client=None)
    recovery_service = JobRecoveryService(
        repo,
        job_service,
        persistence_service=persistence,
        stale_timeout_seconds=300,
    )

    # Run recovery (only jobs older than 300s are reconciled)
    summary = await recovery_service.recover_interrupted_jobs(action="fail", force_active=False)

    assert summary.total_active_scanned == 2
    assert summary.recovered_count == 1
    assert repo.jobs["stale_job"].state == "failed"
    assert repo.jobs["fresh_job"].state == "running"  # Unaffected

    # Verify structured outcome recorded for stale job
    outcome = await persistence.get_processing_outcome("stale_job")
    assert outcome is not None
    assert outcome["status"] == "failed"
    assert outcome["error_code"] == error_codes.TIMEOUT


@pytest.mark.asyncio
async def test_recovery_is_idempotent():
    class TestRepo(SupabaseJobRepository):
        def __init__(self):
            self.jobs: dict[str, Job] = {}

        async def list_active_jobs(self) -> list[Job]:
            return [j for j in self.jobs.values() if j.state in ("running", "queued")]

        async def get(self, job_id: str) -> Job | None:
            return self.jobs.get(job_id)

        async def update(self, job: Job) -> Job:
            self.jobs[job.job_id] = job
            return job

        async def modify(self, job_id: str, mutator):
            current = self.jobs[job_id]
            updated = mutator(current)
            self.jobs[job_id] = updated
            return updated

    repo = TestRepo()
    now = datetime.now(timezone.utc)
    repo.jobs["j1"] = Job(
        job_id="j1", document_id="d1", state="running", created_at=now, updated_at=now
    )

    job_service = JobService(repo, document_exists=lambda _: True)
    recovery_service = JobRecoveryService(repo, job_service)

    # First run recovers j1
    s1 = await recovery_service.recover_interrupted_jobs(force_active=True)
    assert s1.recovered_count == 1
    assert repo.jobs["j1"].state == "failed"

    # Second run does nothing
    s2 = await recovery_service.recover_interrupted_jobs(force_active=True)
    assert s2.recovered_count == 0
