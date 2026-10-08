"""Checkpoint 10: job management tests. No real data/uploads writes."""

import asyncio
import inspect
import io
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import get_args

import pytest
from fastapi.testclient import TestClient
from pydantic import TypeAdapter, ValidationError

from backend.app.api.ingest import get_ingestion_service
from backend.app.api.jobs import get_job_repository
from backend.app.core import error_codes
from backend.app.main import app
from backend.app.models.api_errors import ApiError
from backend.app.models.api_responses import (
    ApiResponse,
    FailureResponse,
    ProcessingData,
    ProcessingResponse,
    Progress,
    SuccessResponse,
)
from backend.app.models.jobs import (
    ACTIVE_STATES,
    ALLOWED_TRANSITIONS,
    TERMINAL_STATES,
    CreateJobRequest,
    DocumentNotFoundError,
    InvalidJobRequestError,
    InvalidJobStateTransitionError,
    Job,
    JobNotFoundError,
    JobState,
)
from backend.app.repositories.job_repository import DuplicateJobError, InMemoryJobRepository
from backend.app.services.ingestion_service import IngestionService
from backend.app.services.job_service import JobService

JobAdapter = TypeAdapter(ApiResponse[Job])
ALL_STATES = list(get_args(JobState))
DOC = "doc_001"

# Independent copy of the spec, so the implementation table is checked against it.
EXPECTED = {
    "queued": {"running", "cancelled", "failed"},
    "running": {"retry_wait", "escalating", "completed", "failed", "cancelled"},
    "retry_wait": {"running", "failed", "cancelled"},
    "escalating": {"running", "completed", "failed", "cancelled"},
    "completed": set(),
    "failed": set(),
    "cancelled": set(),
}
PATHS = {
    "queued": [],
    "running": ["running"],
    "retry_wait": ["running", "retry_wait"],
    "escalating": ["running", "escalating"],
    "completed": ["running", "completed"],
    "failed": ["failed"],
    "cancelled": ["cancelled"],
}


def run(coro):
    return asyncio.run(coro)


class FakeClock:
    """Strictly increasing clock so timestamp assertions are deterministic."""

    def __init__(self):
        self.now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    def __call__(self):
        self.now += timedelta(seconds=1)
        return self.now


@pytest.fixture
def repo():
    return InMemoryJobRepository()


@pytest.fixture
def service(repo):
    return JobService(repo, document_exists=lambda _id: True, clock=FakeClock())


def make_job(job_id="job_1", **overrides):
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    data = {
        "job_id": job_id, "document_id": DOC, "state": "queued", "stage": "queued",
        "created_at": now, "updated_at": now,
    }
    data.update(overrides)
    return Job.model_validate(data)


def reach(service, job_id, state):
    for step in PATHS[state]:
        run(service.transition_job(job_id, step))


# ================================================================ model
def test_state_table_matches_spec():
    assert set(ALLOWED_TRANSITIONS) == set(ALL_STATES) == set(EXPECTED)
    for state, targets in EXPECTED.items():
        assert set(ALLOWED_TRANSITIONS[state]) == targets


def test_active_states_match_checkpoint_8_processing_states():
    c8_states = set(get_args(ProcessingData.model_fields["state"].annotation))
    assert set(ACTIVE_STATES) == c8_states
    assert set(TERMINAL_STATES) == {"completed", "failed", "cancelled"}
    assert set(ACTIVE_STATES) | set(TERMINAL_STATES) == set(ALL_STATES)


def test_job_reuses_checkpoint_8_progress():
    assert Progress in get_args(Job.model_fields["progress"].annotation)


def test_job_rejects_extra_fields_and_bad_values():
    with pytest.raises(ValidationError):
        make_job(extra=1)
    with pytest.raises(ValidationError):
        make_job(state="done")
    for field in ("job_id", "document_id"):
        with pytest.raises(ValidationError):
            make_job(**{field: ""})
    with pytest.raises(ValidationError):
        make_job(stage="")
    with pytest.raises(ValidationError):
        make_job(parent_job_id="")
    with pytest.raises(ValidationError):
        make_job(parent_job_id="job_1")  # own parent


def test_job_timestamps_must_be_aware_and_are_normalized_to_utc():
    with pytest.raises(ValidationError):
        make_job(created_at=datetime(2026, 1, 1), updated_at=datetime(2026, 1, 1))
    tz = timezone(timedelta(hours=5, minutes=30))
    job = make_job(
        created_at=datetime(2026, 1, 1, 5, 30, tzinfo=tz),
        updated_at=datetime(2026, 1, 1, 5, 30, tzinfo=tz),
    )
    assert job.created_at.utcoffset() == timedelta(0)
    assert job.created_at == datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_updated_at_before_created_at_rejected():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with pytest.raises(ValidationError):
        make_job(created_at=now, updated_at=now - timedelta(seconds=1))


def test_job_is_immutable():
    job = make_job()
    with pytest.raises(ValidationError):
        job.state = "running"


def test_create_job_request_rejects_client_job_id_and_empty_values():
    assert CreateJobRequest(document_id="d").parent_job_id is None
    with pytest.raises(ValidationError):
        CreateJobRequest(document_id="d", job_id="client_chosen")
    with pytest.raises(ValidationError):
        CreateJobRequest(document_id="")
    with pytest.raises(ValidationError):
        CreateJobRequest(document_id="d", parent_job_id="")


# ============================================================ repository
def test_repository_create_and_get(repo):
    job = make_job()
    assert run(repo.create(job)) == job
    assert run(repo.get("job_1")) == job


def test_repository_missing_job(repo):
    assert run(repo.get("nope")) is None
    with pytest.raises(JobNotFoundError):
        run(repo.update(make_job("nope")))
    with pytest.raises(JobNotFoundError):
        run(repo.modify("nope", lambda j: j))
    assert run(repo.delete("nope")) is False


def test_repository_duplicate_create_rejected(repo):
    run(repo.create(make_job()))
    with pytest.raises(DuplicateJobError):
        run(repo.create(make_job()))


def test_repository_update(repo):
    run(repo.create(make_job()))
    run(repo.update(make_job(state="running")))
    assert run(repo.get("job_1")).state == "running"


def test_repository_modify_is_all_or_nothing(repo):
    run(repo.create(make_job()))

    def boom(job):
        raise RuntimeError("fail")

    with pytest.raises(RuntimeError):
        run(repo.modify("job_1", boom))
    assert run(repo.get("job_1")).state == "queued"
    with pytest.raises(ValueError):
        run(repo.modify("job_1", lambda j: make_job("other")))


def test_repository_isolation_between_jobs(repo):
    run(repo.create(make_job("a")))
    run(repo.create(make_job("b")))
    run(repo.update(make_job("a", state="running")))
    assert run(repo.get("a")).state == "running"
    assert run(repo.get("b")).state == "queued"


def test_repository_returns_copies_not_internal_objects(repo):
    run(repo.create(make_job(progress={"unit": "pages", "completed": 1, "total": 5})))
    first = run(repo.get("job_1"))
    first.progress.completed = 99  # mutate the returned copy
    assert run(repo.get("job_1")).progress.completed == 1
    assert run(repo.get("job_1")) is not run(repo.get("job_1"))


def test_repository_delete_and_clear(repo):
    run(repo.create(make_job("a")))
    run(repo.create(make_job("b")))
    assert run(repo.delete("a")) is True
    assert run(repo.get("a")) is None
    run(repo.clear())
    assert run(repo.get("b")) is None


def test_repository_lock_under_thread_contention(repo):
    run(repo.create(make_job(progress={"unit": "n", "completed": 0})))

    def bump(job):
        p = job.progress
        return Job.model_validate(
            {**job.model_dump(), "progress": {"unit": p.unit, "completed": p.completed + 1}}
        )

    def worker():
        for _ in range(50):
            asyncio.run(repo.modify("job_1", bump))

    with ThreadPoolExecutor(max_workers=8) as pool:
        for future in [pool.submit(worker) for _ in range(8)]:
            future.result()
    assert run(repo.get("job_1")).progress.completed == 400


def test_repository_concurrent_creates(repo):
    def worker(i):
        asyncio.run(repo.create(make_job(f"job_{i}")))

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(worker, range(100)))
    assert all(run(repo.get(f"job_{i}")) is not None for i in range(100))


# ============================================================== creation
def test_create_job(service):
    job = run(service.create_job(DOC))
    assert uuid.UUID(job.job_id).version == 4
    assert job.document_id == DOC
    assert job.state == "queued"
    assert job.stage == "queued"
    assert job.progress is None
    assert job.parent_job_id is None
    assert job.created_at.tzinfo is not None and job.created_at.utcoffset() == timedelta(0)
    assert job.updated_at == job.created_at


def test_each_job_gets_a_unique_server_generated_id(service):
    assert run(service.create_job(DOC)).job_id != run(service.create_job(DOC)).job_id
    assert "job_id" not in inspect.signature(JobService.create_job).parameters


def test_create_job_with_parent(service):
    parent = run(service.create_job(DOC))
    child = run(service.create_job(DOC, parent_job_id=parent.job_id))
    assert child.parent_job_id == parent.job_id


def test_create_job_with_unknown_parent_rejected(service):
    with pytest.raises(InvalidJobRequestError) as info:
        run(service.create_job(DOC, parent_job_id="missing"))
    assert info.value.field_path == ["body", "parent_job_id"]


@pytest.mark.parametrize("doc", ["", "   "])
def test_create_job_with_empty_document_id_rejected(service, doc):
    with pytest.raises(InvalidJobRequestError):
        run(service.create_job(doc))


def test_create_job_for_missing_document_rejected(repo):
    svc = JobService(repo, document_exists=lambda _id: False)
    with pytest.raises(DocumentNotFoundError):
        run(svc.create_job(DOC))
    assert run(repo.get("anything")) is None


def test_get_job(service):
    job = run(service.create_job(DOC))
    assert run(service.get_job(job.job_id)) == job
    with pytest.raises(JobNotFoundError):
        run(service.get_job("missing"))


# ============================================================ transitions
@pytest.mark.parametrize("src", ALL_STATES)
@pytest.mark.parametrize("dst", ALL_STATES)
def test_every_transition_pair(service, src, dst):
    job = run(service.create_job(DOC))
    reach(service, job.job_id, src)
    before = run(service.get_job(job.job_id))
    assert before.state == src

    if dst in EXPECTED[src]:
        after = run(service.transition_job(job.job_id, dst))
        assert after.state == dst
        assert after.updated_at > before.updated_at
        assert after.created_at == before.created_at
    else:
        with pytest.raises(InvalidJobStateTransitionError):
            run(service.transition_job(job.job_id, dst))
        assert run(service.get_job(job.job_id)) == before  # nothing silently changed


def test_unknown_target_state_rejected(service):
    job = run(service.create_job(DOC))
    with pytest.raises(InvalidJobStateTransitionError):
        run(service.transition_job(job.job_id, "teleporting"))
    assert run(service.get_job(job.job_id)).state == "queued"


def test_transition_unknown_job(service):
    with pytest.raises(JobNotFoundError):
        run(service.transition_job("missing", "running"))


@pytest.mark.parametrize("state", sorted(TERMINAL_STATES))
def test_terminal_states_cannot_transition_anywhere(service, state):
    job = run(service.create_job(DOC))
    reach(service, job.job_id, state)
    for target in ALL_STATES:
        with pytest.raises(InvalidJobStateTransitionError):
            run(service.transition_job(job.job_id, target))


def test_retry_cycle_is_allowed(service):
    job = run(service.create_job(DOC))
    for step in ["running", "retry_wait", "running", "escalating", "running", "completed"]:
        assert run(service.transition_job(job.job_id, step)).state == step


# ================================================================ progress
def test_update_progress_and_stage(service):
    job = run(service.create_job(DOC))
    updated = run(service.update_progress(job.job_id, Progress(unit="pages", completed=2, total=10)))
    assert updated.progress.completed == 2 and updated.progress.total == 10
    assert updated.updated_at > job.updated_at
    assert updated.created_at == job.created_at

    again = run(service.update_progress(job.job_id, Progress(unit="pages", completed=5, total=10)))
    assert again.progress.completed == 5
    assert run(service.update_progress(job.job_id, None)).progress is None

    staged = run(service.update_stage(job.job_id, "extraction"))
    assert staged.stage == "extraction"


def test_invalid_progress_rejected_by_existing_model():
    with pytest.raises(ValidationError):
        Progress(unit="pages", completed=11, total=10)
    with pytest.raises(ValidationError):
        Progress(unit="", completed=1)


def test_empty_stage_rejected_and_state_unchanged(service):
    job = run(service.create_job(DOC))
    with pytest.raises(ValidationError):
        run(service.update_stage(job.job_id, ""))
    assert run(service.get_job(job.job_id)).stage == "queued"


@pytest.mark.parametrize("state", sorted(TERMINAL_STATES))
def test_terminal_jobs_reject_progress_and_stage_updates(service, state):
    job = run(service.create_job(DOC))
    reach(service, job.job_id, state)
    with pytest.raises(InvalidJobStateTransitionError):
        run(service.update_progress(job.job_id, Progress(unit="p", completed=1)))
    with pytest.raises(InvalidJobStateTransitionError):
        run(service.update_stage(job.job_id, "x"))


def test_progress_update_unknown_job(service):
    with pytest.raises(JobNotFoundError):
        run(service.update_progress("missing", None))


# ===================================================================== API
@pytest.fixture
def api(tmp_path):
    repo = InMemoryJobRepository()
    ingestion = IngestionService(upload_root=tmp_path / "uploads")
    app.dependency_overrides[get_job_repository] = lambda: repo
    app.dependency_overrides[get_ingestion_service] = lambda: ingestion
    yield SimpleNamespace(
        client=TestClient(app),
        repo=repo,
        tmp=tmp_path,
        service=JobService(repo, document_exists=lambda _id: True),
    )
    app.dependency_overrides.pop(get_job_repository, None)
    app.dependency_overrides.pop(get_ingestion_service, None)


@pytest.fixture
def document_id(api):
    response = api.client.post(
        "/v1/ingest", files={"file": ("a.pdf", b"%PDF-1.7 test", "application/pdf")}
    )
    assert response.status_code == 201
    return response.json()["data"]["document_id"]


def post_job(api, **body):
    return api.client.post("/v1/jobs", json=body)


def parse(response):
    return JobAdapter.validate_python(response.json())


def create_via_api(api, document_id, **extra):
    response = post_job(api, document_id=document_id, **extra)
    assert response.status_code == 202
    return parse(response)


def assert_failure(response, status, code, category="request"):
    assert response.status_code == status
    parsed = parse(response)
    assert isinstance(parsed, FailureResponse)
    assert parsed.errors and parsed.request_id and parsed.data is None
    error = parsed.errors[0]
    assert (error.code, error.category) == (code, category)
    assert isinstance(error, ApiError)
    return parsed


def test_post_jobs_returns_202_processing_response(api, document_id):
    response = post_job(api, document_id=document_id)
    assert response.status_code == 202
    parsed = parse(response)
    assert isinstance(parsed, ProcessingResponse)

    data = parsed.data
    assert data.state == "queued"
    assert data.stage == "queued"
    assert data.progress is None
    assert data.partial_result is None
    assert data.poll_after_seconds > 0
    assert data.parent_job_id is None
    assert data.job_url == f"/v1/jobs/{parsed.job_id}"
    assert uuid.UUID(parsed.job_id).version == 4
    assert parsed.document_id == document_id
    assert parsed.request_id
    assert parsed.response_version == "1.0"
    assert parsed.errors == [] and parsed.meta == {}
    assert response.headers["location"] == data.job_url


def test_job_url_is_logical_and_machine_independent(api, document_id):
    response = post_job(api, document_id=document_id)
    url = response.json()["data"]["job_url"]
    assert url.startswith("/v1/jobs/")
    assert "://" not in url and "localhost" not in url and "\\" not in url
    assert str(api.tmp) not in response.text


def test_post_jobs_with_parent(api, document_id):
    parent = create_via_api(api, document_id)
    child = create_via_api(api, document_id, parent_job_id=parent.job_id)
    assert child.data.parent_job_id == parent.job_id


def test_post_jobs_unknown_parent_rejected(api, document_id):
    parsed = assert_failure(
        post_job(api, document_id=document_id, parent_job_id="nope"),
        400, error_codes.REQUEST_VALIDATION_FAILED,
    )
    assert parsed.errors[0].location.field_path == ["body", "parent_job_id"]


def test_client_cannot_supply_job_id(api, document_id):
    assert_failure(
        post_job(api, document_id=document_id, job_id="client_chosen"),
        400, error_codes.REQUEST_VALIDATION_FAILED,
    )
    assert run(api.repo.get("client_chosen")) is None


@pytest.mark.parametrize("content", [b"", b"not json", b"[]", b'{"parent_job_id": "x"}', b'{"document_id": ""}'])
def test_invalid_bodies_return_standard_failure(api, content):
    response = api.client.post("/v1/jobs", content=content)
    assert_failure(response, 400, error_codes.REQUEST_VALIDATION_FAILED)


@pytest.mark.parametrize("bad_id", ["doc_001", "../../etc/passwd", "00000000-0000-4000-8000-000000000000", "x" * 300])
def test_missing_document_returns_document_unavailable(api, bad_id):
    parsed = assert_failure(post_job(api, document_id=bad_id), 404, error_codes.DOCUMENT_UNAVAILABLE)
    assert parsed.errors[0].location.field_path == ["body", "document_id"]
    assert bad_id not in parsed.message


def test_document_checked_against_c9_storage_only_when_stored(api, document_id):
    assert post_job(api, document_id=document_id).status_code == 202


def test_get_active_job_returns_processing_response(api, document_id):
    created = create_via_api(api, document_id)
    response = api.client.get(f"/v1/jobs/{created.job_id}")
    assert response.status_code == 200
    parsed = parse(response)
    assert isinstance(parsed, ProcessingResponse)
    assert parsed.job_id == created.job_id and parsed.document_id == document_id
    assert parsed.data.job_url == f"/v1/jobs/{created.job_id}"


@pytest.mark.parametrize("state", sorted(ACTIVE_STATES))
def test_every_active_state_is_a_processing_response(api, document_id, state):
    created = create_via_api(api, document_id)
    reach(api.service, created.job_id, state)
    run(api.service.update_progress(created.job_id, Progress(unit="pages", completed=1, total=4)))
    parsed = parse(api.client.get(f"/v1/jobs/{created.job_id}"))
    assert isinstance(parsed, ProcessingResponse)
    assert parsed.data.state == state
    assert parsed.data.progress.completed == 1


def test_completed_job_returns_success_response(api, document_id):
    created = create_via_api(api, document_id)
    reach(api.service, created.job_id, "completed")
    response = api.client.get(f"/v1/jobs/{created.job_id}")
    assert response.status_code == 200
    parsed = parse(response)
    assert isinstance(parsed, SuccessResponse)
    assert parsed.data.state == "completed"
    assert parsed.data.job_id == parsed.job_id == created.job_id
    assert parsed.document_id == parsed.data.document_id == document_id
    assert parsed.errors == []


def test_cancelled_job_returns_success_response(api, document_id):
    created = create_via_api(api, document_id)
    reach(api.service, created.job_id, "cancelled")
    parsed = parse(api.client.get(f"/v1/jobs/{created.job_id}"))
    assert isinstance(parsed, SuccessResponse)
    assert parsed.data.state == "cancelled"


def test_failed_job_returns_failure_response_with_http_200(api, document_id):
    created = create_via_api(api, document_id)
    reach(api.service, created.job_id, "failed")
    response = api.client.get(f"/v1/jobs/{created.job_id}")
    assert response.status_code == 200
    parsed = parse(response)
    assert isinstance(parsed, FailureResponse)
    assert parsed.data is None
    assert len(parsed.errors) >= 1
    assert parsed.job_id == created.job_id and parsed.document_id == document_id
    assert parsed.errors[0].recoverable is False and parsed.errors[0].recovery is None


def test_unknown_job_returns_404_job_not_found(api):
    parsed = assert_failure(api.client.get("/v1/jobs/does-not-exist"), 404, error_codes.JOB_NOT_FOUND)
    assert parsed.errors[0].code != error_codes.DOCUMENT_UNAVAILABLE
    assert parsed.errors[0].location.field_path == ["path", "job_id"]
    assert parsed.job_id is None


def test_error_ids_and_request_ids_are_unique(api):
    bodies = [api.client.get(f"/v1/jobs/missing{i}").json() for i in range(3)]
    assert len({b["errors"][0]["error_id"] for b in bodies}) == 3
    assert len({b["request_id"] for b in bodies}) == 3


def test_jobs_are_isolated_through_the_api(api, document_id):
    a = create_via_api(api, document_id)
    b = create_via_api(api, document_id)
    reach(api.service, a.job_id, "running")
    assert parse(api.client.get(f"/v1/jobs/{a.job_id}")).data.state == "running"
    assert parse(api.client.get(f"/v1/jobs/{b.job_id}")).data.state == "queued"


@pytest.mark.parametrize("method,path,kwargs", [
    ("post", "/v1/jobs", {"content": b"{}"}),
    ("get", "/v1/jobs/missing", {}),
])
def test_failure_envelopes_contain_all_keys_and_no_internals(api, method, path, kwargs):
    response = getattr(api.client, method)(path, **kwargs)
    body = response.json()
    assert set(body) == {
        "response_version", "status", "request_id", "message",
        "job_id", "document_id", "data", "errors", "meta",
    }
    assert body["status"] == "failure" and body["errors"]
    for leak in ("Traceback", str(api.tmp), "InMemoryJobRepository", "_jobs"):
        assert leak not in response.text


def test_existing_endpoints_still_work(api):
    assert api.client.get("/v1/health").status_code == 200
    empty = api.client.post("/v1/ingest", files={"file": ("a.pdf", b"", "application/pdf")})
    assert empty.status_code == 400


# ==================================================== C9 document lookup
class BytesReader:
    def __init__(self, data):
        self._buf = io.BytesIO(data)

    async def read(self, size=-1):
        return self._buf.read(size)


def test_ingestion_has_document(tmp_path):
    ingestion = IngestionService(upload_root=tmp_path / "uploads")
    stored = run(ingestion.ingest(filename="a.png", content_type="image/png", reader=BytesReader(b"x")))
    assert ingestion.has_document(stored.document_id) is True
    assert ingestion.has_document(str(uuid.uuid4())) is False
    assert ingestion.has_document("../uploads/x") is False
    assert ingestion.has_document("") is False


def test_in_progress_part_files_do_not_count_as_documents(tmp_path):
    root = tmp_path / "uploads"
    root.mkdir()
    doc = str(uuid.uuid4())
    (root / f"{doc}.pdf.part").write_bytes(b"partial")
    assert IngestionService(upload_root=root).has_document(doc) is False


# ======================================================== error code registry
def test_new_error_codes_are_open_string_constants():
    from backend.app.models.api_errors import ApiError

    assert error_codes.JOB_NOT_FOUND == "JOB_NOT_FOUND"
    assert error_codes.INVALID_JOB_STATE_TRANSITION == "INVALID_JOB_STATE_TRANSITION"
    for code in (error_codes.JOB_NOT_FOUND, error_codes.INVALID_JOB_STATE_TRANSITION):
        err = ApiError(error_id="e1", code=code, category="request", message="m", recoverable=False)
        assert err.code == code
    # The Checkpoint 8 registry is intentionally left unchanged.
    assert len(error_codes.KNOWN_ERROR_CODES) == 15
    assert error_codes.JOB_NOT_FOUND not in error_codes.KNOWN_ERROR_CODES
    assert error_codes.JOB_ERROR_CODES == {
        error_codes.JOB_NOT_FOUND, error_codes.INVALID_JOB_STATE_TRANSITION,
    }
