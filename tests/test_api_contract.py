"""Checkpoint 8: API response/error contract tests."""

import json
import sys
from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from backend.app.core import error_codes
from backend.app.models import api_responses
from backend.app.models.api_base import ApiModel
from backend.app.models.api_errors import (
    ApiError,
    DocumentLocation,
    ErrorLocation,
    PageLocation,
    RecoveryHint,
    RegionLocation,
    RequestLocation,
)
from backend.app.models.api_responses import (
    ApiResponse,
    ConfidenceSignal,
    DocumentData,
    DocumentResult,
    FailureResponse,
    GraphReference,
    PartialSuccessResponse,
    ProcessingData,
    ProcessingResponse,
    Progress,
    QualitySummary,
    RiskSignal,
    SuccessResponse,
)
from backend.app.models.document_graph import Document

REPO_ROOT = Path(__file__).resolve().parents[1]
MOCK_OUTPUT = Path(__file__).parent / "mock_output.json"

ENVELOPE_KEYS = {
    "response_version",
    "status",
    "request_id",
    "message",
    "job_id",
    "document_id",
    "data",
    "errors",
    "meta",
}


class Payload(ApiModel):
    """Simple typed endpoint payload used to exercise the generics."""

    value: int


PayloadResponse = TypeAdapter(ApiResponse[Payload])
LocationAdapter = TypeAdapter(ErrorLocation)


# ------------------------------------------------------------------ builders
def make_error(**overrides):
    data = {
        "error_id": "err_001",
        "code": error_codes.PARSE_FAILED,
        "category": "processing",
        "message": "The document could not be parsed.",
        "recoverable": False,
    }
    data.update(overrides)
    return data


def retry_error(**overrides):
    return make_error(
        code=error_codes.TIMEOUT,
        recoverable=True,
        recovery={"action": "retry", "owner": "client", "retry_after_seconds": 5},
        **overrides,
    )


def processing_data(**overrides):
    data = {
        "job_url": "/api/v1/jobs/job_001",
        "state": "running",
        "poll_after_seconds": 2,
    }
    data.update(overrides)
    return data


def success_payload(**overrides):
    data = {
        "status": "success",
        "request_id": "req_001",
        "message": "Done.",
        "data": {"value": 1},
    }
    data.update(overrides)
    return data


def processing_payload(**overrides):
    data = {
        "status": "processing",
        "request_id": "req_001",
        "message": "Processing.",
        "job_id": "job_001",
        "data": processing_data(),
    }
    data.update(overrides)
    return data


def partial_payload(**overrides):
    data = {
        "status": "partial_success",
        "request_id": "req_001",
        "message": "Partially processed.",
        "data": {"value": 1},
        "errors": [make_error(category="quality", code=error_codes.TABLE_EXTRACTION_FAILED)],
    }
    data.update(overrides)
    return data


def failure_payload(**overrides):
    data = {
        "status": "failure",
        "request_id": "req_001",
        "message": "Request failed.",
        "data": None,
        "errors": [make_error()],
    }
    data.update(overrides)
    return data


def graph_ref_data(**overrides):
    data = {
        "schema_version": "1.0",
        "revision": "rev_001",
        "url": "/api/v1/documents/doc_001/graph",
    }
    data.update(overrides)
    return data


def quality_data(**overrides):
    data = {
        "completeness": "complete",
        "fidelity": "pass",
        "confidence": {"value": 0.92, "method": "heuristic_v1"},
        "risk": {"level": "low", "method": "rule_based_v1"},
    }
    data.update(overrides)
    return data


@pytest.fixture(scope="module")
def document():
    raw = json.loads(MOCK_OUTPUT.read_text(encoding="utf-8"))
    return Document.model_validate(raw)


# ===================================================== 1-4: response states
def test_valid_success_response():
    resp = PayloadResponse.validate_python(success_payload())
    assert isinstance(resp, SuccessResponse)
    assert resp.status == "success"
    assert resp.data.value == 1


def test_valid_processing_response():
    resp = PayloadResponse.validate_python(processing_payload())
    assert isinstance(resp, ProcessingResponse)
    assert resp.job_id == "job_001"
    assert resp.data.state == "running"


def test_valid_partial_success_response():
    resp = PayloadResponse.validate_python(partial_payload())
    assert isinstance(resp, PartialSuccessResponse)
    assert len(resp.errors) == 1


def test_valid_failure_response():
    resp = PayloadResponse.validate_python(failure_payload())
    assert isinstance(resp, FailureResponse)
    assert resp.data is None


# ================================================== 5-12: state invariants
def test_success_with_errors_rejected():
    with pytest.raises(ValidationError):
        PayloadResponse.validate_python(success_payload(errors=[make_error()]))


def test_success_with_null_data_rejected():
    with pytest.raises(ValidationError):
        PayloadResponse.validate_python(success_payload(data=None))


def test_partial_success_without_errors_rejected():
    with pytest.raises(ValidationError):
        PayloadResponse.validate_python(partial_payload(errors=[]))


def test_partial_success_with_null_data_rejected():
    with pytest.raises(ValidationError):
        PayloadResponse.validate_python(partial_payload(data=None))


def test_failure_with_data_rejected():
    with pytest.raises(ValidationError):
        PayloadResponse.validate_python(failure_payload(data={"value": 1}))


def test_failure_without_errors_rejected():
    with pytest.raises(ValidationError):
        PayloadResponse.validate_python(failure_payload(errors=[]))


def test_processing_without_job_id_rejected():
    with pytest.raises(ValidationError):
        PayloadResponse.validate_python(processing_payload(job_id=None))
    payload = processing_payload()
    del payload["job_id"]
    with pytest.raises(ValidationError):
        PayloadResponse.validate_python(payload)


def test_processing_with_valid_processing_data_accepted():
    resp = PayloadResponse.validate_python(
        processing_payload(
            data=processing_data(
                state="retry_wait",
                stage="extraction",
                progress={"unit": "pages", "completed": 2, "total": 10},
                partial_result={"value": 7},
                parent_job_id="job_000",
            ),
            errors=[retry_error()],
        )
    )
    assert resp.data.partial_result.value == 7
    assert resp.data.parent_job_id == "job_000"
    assert len(resp.errors) == 1  # unresolved issues are allowed while processing


# ========================================================= 13-18: ApiError
def test_valid_api_error():
    err = ApiError.model_validate(make_error())
    assert err.code == "PARSE_FAILED"
    assert err.recovery is None
    assert err.stage is None
    assert err.location is None
    assert err.details == {}


def test_valid_recoverable_error_with_everything():
    err = ApiError.model_validate(
        retry_error(
            stage="extraction",
            location={"scope": "page", "document_id": "doc_001", "page_number": 3},
            details={"attempt": 2, "tags": ["a", "b"], "nested": {"ok": True, "none": None}},
        )
    )
    assert err.recovery.action == "retry"
    assert isinstance(err.location, PageLocation)


@pytest.mark.parametrize(
    "code",
    ["parse_failed", "1PARSE", "_PARSE", "PARSE-FAILED", "PARSE FAILED", "", "A" * 65, "PARSE_FAILED\n"],
)
def test_invalid_error_code_format_rejected(code):
    with pytest.raises(ValidationError):
        ApiError.model_validate(make_error(code=code))


def test_recoverable_false_with_recovery_rejected():
    with pytest.raises(ValidationError):
        ApiError.model_validate(
            make_error(recoverable=False, recovery={"action": "retry", "owner": "server"})
        )


def test_recoverable_true_without_recovery_rejected():
    with pytest.raises(ValidationError):
        ApiError.model_validate(make_error(recoverable=True))
    with pytest.raises(ValidationError):
        ApiError.model_validate(make_error(recoverable=True, recovery=None))


def test_negative_retry_after_seconds_rejected():
    with pytest.raises(ValidationError):
        RecoveryHint(action="retry", owner="client", retry_after_seconds=-1)


def test_escalation_with_retry_delay_rejected():
    with pytest.raises(ValidationError):
        RecoveryHint(action="escalate", owner="server", retry_after_seconds=10)


def test_escalation_without_retry_delay_accepted():
    hint = RecoveryHint(action="escalate", owner="server")
    assert hint.retry_after_seconds is None


def test_retry_after_zero_accepted():
    assert RecoveryHint(action="retry", owner="client", retry_after_seconds=0).retry_after_seconds == 0


def test_recovery_hint_invalid_action_or_owner_rejected():
    with pytest.raises(ValidationError):
        RecoveryHint(action="abort", owner="server")
    with pytest.raises(ValidationError):
        RecoveryHint(action="retry", owner="nobody")


def test_invalid_category_rejected():
    with pytest.raises(ValidationError):
        ApiError.model_validate(make_error(category="network"))


@pytest.mark.parametrize("category", ["request", "processing", "quality", "dependency", "internal"])
def test_all_categories_accepted(category):
    assert ApiError.model_validate(make_error(category=category)).category == category


@pytest.mark.parametrize("field", ["error_id", "message"])
@pytest.mark.parametrize("value", ["", "   "])
def test_empty_error_strings_rejected(field, value):
    with pytest.raises(ValidationError):
        ApiError.model_validate(make_error(**{field: value}))


def test_unknown_error_codes_accepted():
    code = "SOME_FUTURE_CODE_2"
    assert code not in error_codes.KNOWN_ERROR_CODES
    assert ApiError.model_validate(make_error(code=code)).code == code
    assert ApiError.model_validate(make_error(code="A" * 64)).code == "A" * 64


def test_recoverable_must_be_a_real_bool():
    with pytest.raises(ValidationError):
        ApiError.model_validate(make_error(recoverable="false"))


# ====================================================== 19-24: locations
def test_valid_request_location():
    loc = LocationAdapter.validate_python({"scope": "request", "field_path": ["body", "file"]})
    assert isinstance(loc, RequestLocation)
    assert loc.field_path == ["body", "file"]


def test_valid_document_location():
    loc = LocationAdapter.validate_python({"scope": "document", "document_id": "doc_001"})
    assert isinstance(loc, DocumentLocation)


def test_valid_page_location():
    loc = LocationAdapter.validate_python(
        {"scope": "page", "document_id": "doc_001", "page_number": 1}
    )
    assert isinstance(loc, PageLocation)
    assert loc.page_number == 1


def test_valid_region_location():
    loc = LocationAdapter.validate_python(
        {
            "scope": "region",
            "document_id": "doc_001",
            "page_number": 2,
            "region_id": "block_7",
            "graph_revision": "rev_001",
            "graph_pointer": "/pages/1/blocks/6",
        }
    )
    assert isinstance(loc, RegionLocation)
    assert loc.graph_pointer == "/pages/1/blocks/6"


@pytest.mark.parametrize("page_number", [0, -1, "1", 1.5, True, None])
def test_invalid_page_number_rejected(page_number):
    with pytest.raises(ValidationError):
        LocationAdapter.validate_python(
            {"scope": "page", "document_id": "doc_001", "page_number": page_number}
        )
    with pytest.raises(ValidationError):
        LocationAdapter.validate_python(
            {
                "scope": "region",
                "document_id": "doc_001",
                "page_number": page_number,
                "region_id": "r1",
            }
        )


@pytest.mark.parametrize(
    "location",
    [
        {"scope": "document", "document_id": "doc_001"},
        {"scope": "page", "document_id": "doc_001", "page_number": 1},
        {"scope": "region", "document_id": "doc_001", "page_number": 1, "region_id": "r1"},
    ],
)
def test_graph_pointer_without_graph_revision_rejected(location):
    with pytest.raises(ValidationError):
        LocationAdapter.validate_python({**location, "graph_pointer": "/pages/0"})


@pytest.mark.parametrize(
    "location",
    [
        {"scope": "document", "document_id": "doc_001"},
        {"scope": "page", "document_id": "doc_001", "page_number": 1},
        {"scope": "region", "document_id": "doc_001", "page_number": 1, "region_id": "r1"},
    ],
)
def test_graph_revision_alone_and_with_pointer_accepted(location):
    assert LocationAdapter.validate_python({**location, "graph_revision": "rev_001"})
    assert LocationAdapter.validate_python(
        {**location, "graph_revision": "rev_001", "graph_pointer": "/pages/0"}
    )


def test_empty_graph_pointer_or_revision_rejected():
    base = {"scope": "document", "document_id": "doc_001"}
    with pytest.raises(ValidationError):
        LocationAdapter.validate_python({**base, "graph_revision": ""})
    with pytest.raises(ValidationError):
        LocationAdapter.validate_python({**base, "graph_revision": "rev_001", "graph_pointer": ""})


@pytest.mark.parametrize(
    "location",
    [
        {"scope": "request", "field_path": []},
        {"scope": "request", "field_path": [""]},
        {"scope": "request", "field_path": ["body", "  "]},
        {"scope": "request", "field_path": "body.file"},  # must be a list
        {"scope": "request"},
        {"scope": "request", "field_path": ["body"], "document_id": "doc_001"},
    ],
)
def test_invalid_request_locations_rejected(location):
    with pytest.raises(ValidationError):
        LocationAdapter.validate_python(location)


def test_location_missing_required_fields_rejected():
    with pytest.raises(ValidationError):
        LocationAdapter.validate_python({"scope": "document"})
    with pytest.raises(ValidationError):
        LocationAdapter.validate_python({"scope": "page", "document_id": "doc_001"})
    with pytest.raises(ValidationError):
        LocationAdapter.validate_python(
            {"scope": "region", "document_id": "doc_001", "page_number": 1}
        )


def test_unknown_location_scope_rejected():
    with pytest.raises(ValidationError):
        LocationAdapter.validate_python({"scope": "block", "document_id": "doc_001"})


def test_location_has_no_bbox_fields():
    for model in (RequestLocation, DocumentLocation, PageLocation, RegionLocation):
        assert not {"bbox", "bounding_box", "x", "y", "width", "height"} & set(model.model_fields)
    with pytest.raises(ValidationError):
        LocationAdapter.validate_python(
            {
                "scope": "region",
                "document_id": "doc_001",
                "page_number": 1,
                "region_id": "r1",
                "bbox": [0, 0, 1, 1],
            }
        )


# ======================================================== 25-27: processing
def test_progress_completed_exceeds_total_rejected():
    with pytest.raises(ValidationError):
        Progress(unit="pages", completed=11, total=10)


@pytest.mark.parametrize("completed,total", [(0, 10), (5, 10), (10, 10), (0, 0), (99, None)])
def test_progress_valid(completed, total):
    p = Progress(unit="pages", completed=completed, total=total)
    assert p.completed == completed
    assert p.total == total


def test_progress_total_defaults_to_null():
    assert Progress(unit="pages", completed=3).total is None


@pytest.mark.parametrize("kwargs", [{"completed": -1}, {"completed": 1, "total": -1}, {"unit": ""}])
def test_progress_invalid_fields_rejected(kwargs):
    base = {"unit": "pages", "completed": 1, "total": 2}
    base.update(kwargs)
    with pytest.raises(ValidationError):
        Progress(**base)


def test_invalid_processing_state_rejected():
    with pytest.raises(ValidationError):
        ProcessingData[Payload].model_validate(processing_data(state="done"))


@pytest.mark.parametrize("state", ["queued", "running", "retry_wait", "escalating"])
def test_all_processing_states_accepted(state):
    assert ProcessingData[Payload].model_validate(processing_data(state=state)).state == state


@pytest.mark.parametrize("poll", [0, -1, 1.5, "2"])
def test_poll_after_seconds_must_be_positive_int(poll):
    with pytest.raises(ValidationError):
        ProcessingData[Payload].model_validate(processing_data(poll_after_seconds=poll))


def test_processing_data_nullable_fields_default_to_null():
    pd = ProcessingData[Payload].model_validate(processing_data())
    assert pd.stage is None
    assert pd.progress is None
    assert pd.partial_result is None
    assert pd.parent_job_id is None


def test_processing_data_requires_job_url():
    data = processing_data()
    del data["job_url"]
    with pytest.raises(ValidationError):
        ProcessingData[Payload].model_validate(data)
    with pytest.raises(ValidationError):
        ProcessingData[Payload].model_validate(processing_data(job_url=""))


def test_processing_response_requires_processing_data():
    with pytest.raises(ValidationError):
        PayloadResponse.validate_python(processing_payload(data=None))
    with pytest.raises(ValidationError):
        PayloadResponse.validate_python(processing_payload(data={"value": 1}))


# ============================================================ 28-30: quality
@pytest.mark.parametrize("value", [-0.01, 1.01, 2, float("nan"), float("inf"), float("-inf")])
def test_confidence_outside_unit_interval_rejected(value):
    with pytest.raises(ValidationError):
        ConfidenceSignal(value=value, method="heuristic_v1")


@pytest.mark.parametrize("value", [0, 0.0, 0.5, 1, 1.0])
def test_confidence_boundaries_accepted(value):
    assert ConfidenceSignal(value=value, method="heuristic_v1").value == value


def test_invalid_risk_level_rejected():
    with pytest.raises(ValidationError):
        RiskSignal(level="critical", method="rule_based_v1")


@pytest.mark.parametrize("level", ["low", "medium", "high"])
def test_risk_levels_accepted(level):
    assert RiskSignal(level=level, method="rule_based_v1").level == level


@pytest.mark.parametrize("method", ["", "   "])
def test_empty_method_rejected(method):
    with pytest.raises(ValidationError):
        ConfidenceSignal(value=0.5, method=method)
    with pytest.raises(ValidationError):
        RiskSignal(level="low", method=method)


def test_quality_summary_valid_and_nullable_signals():
    q = QualitySummary.model_validate(quality_data(confidence=None, risk=None))
    assert q.confidence is None
    assert q.risk is None


def test_quality_summary_completeness_and_fidelity_are_independent():
    q = QualitySummary(completeness="complete", fidelity="fail")
    assert (q.completeness, q.fidelity) == ("complete", "fail")
    q = QualitySummary(completeness="partial", fidelity="pass")
    assert (q.completeness, q.fidelity) == ("partial", "pass")


@pytest.mark.parametrize(
    "overrides",
    [{"completeness": "full"}, {"fidelity": "ok"}, {"fidelity": None}, {"completeness": None}],
)
def test_quality_summary_invalid_values_rejected(overrides):
    with pytest.raises(ValidationError):
        QualitySummary.model_validate(quality_data(**overrides))


def test_quality_summary_has_no_aggregate_confidence_field():
    assert set(QualitySummary.model_fields) == {"completeness", "fidelity", "confidence", "risk"}


def test_graph_reference_validation():
    assert GraphReference.model_validate(graph_ref_data()).schema_version == "1.0"
    with pytest.raises(ValidationError):
        GraphReference.model_validate(graph_ref_data(schema_version="2.0"))
    with pytest.raises(ValidationError):
        GraphReference.model_validate(graph_ref_data(revision=""))
    with pytest.raises(ValidationError):
        GraphReference.model_validate(graph_ref_data(url=""))


# ============================================== 31-33: Document Graph compat
def test_document_result_with_existing_graph_contract():
    result = DocumentResult.model_validate(
        {"graph_ref": graph_ref_data(), "quality": quality_data()}
    )
    assert result.graph_ref.revision == "rev_001"
    # Lightweight: the graph itself is never embedded.
    assert "graph" not in DocumentResult.model_fields
    with pytest.raises(ValidationError):
        DocumentResult.model_validate(
            {"graph": {}, "graph_ref": graph_ref_data(), "quality": quality_data()}
        )


def test_document_data_embeds_existing_document_model(document):
    data = DocumentData(
        graph=document,
        graph_ref=GraphReference.model_validate(graph_ref_data()),
        quality=QualitySummary.model_validate(quality_data()),
    )
    assert isinstance(data.graph, Document)
    assert DocumentData.model_fields["graph"].annotation is Document


def test_document_data_requires_all_parts(document):
    with pytest.raises(ValidationError):
        DocumentData.model_validate({"graph_ref": graph_ref_data(), "quality": quality_data()})
    with pytest.raises(ValidationError):
        DocumentData(graph=document, graph_ref=graph_ref_data())


def test_document_data_in_success_response_roundtrips(document):
    adapter = TypeAdapter(ApiResponse[DocumentData])
    resp = SuccessResponse[DocumentData](
        request_id="req_001",
        message="Document retrieved.",
        document_id="doc_001",
        data=DocumentData(
            graph=document,
            graph_ref=GraphReference.model_validate(graph_ref_data()),
            quality=QualitySummary.model_validate(quality_data()),
        ),
    )
    wire = adapter.dump_json(resp)
    parsed = adapter.validate_json(wire)
    assert isinstance(parsed, SuccessResponse)
    assert isinstance(parsed.data.graph, Document)
    assert adapter.dump_python(parsed, mode="json") == json.loads(wire)


def test_document_result_in_processing_partial_result():
    adapter = TypeAdapter(ApiResponse[DocumentResult])
    resp = adapter.validate_python(
        processing_payload(
            data=processing_data(
                partial_result={"graph_ref": graph_ref_data(), "quality": quality_data()}
            )
        )
    )
    assert isinstance(resp.data.partial_result, DocumentResult)


def test_existing_document_graph_remains_unchanged(document):
    # Document Graph v1.0 is not an API model and carries no API-layer fields.
    assert not issubclass(Document, ApiModel)
    assert Document.__module__ == "backend.app.models.document_graph"
    assert not {"revision", "graph_ref", "quality", "response_version"} & set(Document.model_fields)

    # Building API models around it must not change its schema.
    before = Document.model_json_schema()
    DocumentData(
        graph=document,
        graph_ref=GraphReference.model_validate(graph_ref_data()),
        quality=QualitySummary.model_validate(quality_data()),
    )
    TypeAdapter(ApiResponse[DocumentData]).json_schema()
    assert Document.model_json_schema() == before

    # The model source does not reference the API contract.
    source = (REPO_ROOT / "backend/app/models/document_graph.py").read_text(encoding="utf-8")
    for token in ("api_base", "api_errors", "api_responses", "graph_ref", "ApiModel"):
        assert token not in source


def test_import_identity_and_no_app_root_modules():
    from backend.app.models.document_graph import Document as Canonical

    assert api_responses.Document is Canonical
    assert Document is Canonical
    assert DocumentData.model_fields["graph"].annotation is Canonical
    for name in ("app", "app.models", "app.models.document_graph"):
        assert name not in sys.modules


# ========================================================== 34-37: serialization
def _build_all_variants():
    return [
        PayloadResponse.validate_python(success_payload()),
        PayloadResponse.validate_python(processing_payload()),
        PayloadResponse.validate_python(partial_payload()),
        PayloadResponse.validate_python(failure_payload()),
    ]


def test_success_response_serializes_to_plain_json():
    resp = PayloadResponse.validate_python(success_payload())
    dumped = PayloadResponse.dump_python(resp, mode="json")
    assert json.loads(json.dumps(dumped)) == dumped
    assert type(dumped["status"]) is str
    assert dumped["status"] == "success"
    assert dumped["response_version"] == "1.0"
    assert json.loads(PayloadResponse.dump_json(resp)) == dumped


@pytest.mark.parametrize("index", [0, 1, 2, 3])
def test_all_envelope_keys_serialize_for_every_variant(index):
    resp = _build_all_variants()[index]
    dumped = PayloadResponse.dump_python(resp, mode="json")
    assert set(dumped) == ENVELOPE_KEYS


def test_nullable_envelope_keys_are_present_as_null():
    dumped = PayloadResponse.dump_python(
        PayloadResponse.validate_python(failure_payload()), mode="json"
    )
    assert "job_id" in dumped and dumped["job_id"] is None
    assert "document_id" in dumped and dumped["document_id"] is None
    assert "data" in dumped and dumped["data"] is None


def test_errors_serialize_as_empty_list_not_null():
    dumped = PayloadResponse.dump_python(
        PayloadResponse.validate_python(success_payload()), mode="json"
    )
    assert dumped["errors"] == []


def test_meta_serializes_as_empty_object_not_null():
    dumped = PayloadResponse.dump_python(
        PayloadResponse.validate_python(success_payload()), mode="json"
    )
    assert dumped["meta"] == {}


@pytest.mark.parametrize("payload_fn", [success_payload, processing_payload])
def test_explicit_null_errors_or_meta_rejected(payload_fn):
    with pytest.raises(ValidationError):
        PayloadResponse.validate_python(payload_fn(errors=None))
    with pytest.raises(ValidationError):
        PayloadResponse.validate_python(payload_fn(meta=None))


def test_error_serializes_with_plain_strings_and_nulls():
    err = ApiError.model_validate(retry_error(location={"scope": "document", "document_id": "d1"}))
    dumped = err.model_dump(mode="json")
    assert json.loads(json.dumps(dumped)) == dumped
    assert type(dumped["category"]) is str
    assert dumped["location"]["scope"] == "document"
    assert dumped["stage"] is None
    assert dumped["details"] == {}
    plain = ApiError.model_validate(make_error()).model_dump(mode="json")
    assert plain["recovery"] is None and plain["location"] is None


def test_status_discriminates_variant_from_json():
    expected = {
        "success": SuccessResponse,
        "processing": ProcessingResponse,
        "partial_success": PartialSuccessResponse,
        "failure": FailureResponse,
    }
    for resp in _build_all_variants():
        wire = PayloadResponse.dump_json(resp)
        parsed = PayloadResponse.validate_json(wire)
        assert isinstance(parsed, expected[parsed.status])


def test_unknown_status_rejected():
    with pytest.raises(ValidationError):
        PayloadResponse.validate_python(success_payload(status="ok"))
    payload = success_payload()
    del payload["status"]
    with pytest.raises(ValidationError):
        PayloadResponse.validate_python(payload)


def test_discriminated_union_json_schema_is_keyed_by_status():
    schema = PayloadResponse.json_schema()
    assert schema["discriminator"]["propertyName"] == "status"
    assert set(schema["discriminator"]["mapping"]) == {
        "success",
        "processing",
        "partial_success",
        "failure",
    }


# ============================================== extra: validation hygiene
def test_response_version_must_be_1_0():
    with pytest.raises(ValidationError):
        PayloadResponse.validate_python(success_payload(response_version="2.0"))
    assert PayloadResponse.validate_python(success_payload()).response_version == "1.0"


def test_no_redundant_success_bool():
    with pytest.raises(ValidationError):
        PayloadResponse.validate_python(success_payload(success=True))
    for model in (SuccessResponse, ProcessingResponse, PartialSuccessResponse, FailureResponse):
        assert "success" not in model.model_fields


@pytest.mark.parametrize("field", ["request_id", "message", "job_id", "document_id"])
@pytest.mark.parametrize("value", ["", "   "])
def test_empty_envelope_strings_rejected(field, value):
    with pytest.raises(ValidationError):
        PayloadResponse.validate_python(success_payload(**{field: value}))


def test_unknown_fields_rejected_everywhere():
    with pytest.raises(ValidationError):
        PayloadResponse.validate_python(success_payload(extra_field=1))
    with pytest.raises(ValidationError):
        PayloadResponse.validate_python(success_payload(data={"value": 1, "extra": 2}))
    with pytest.raises(ValidationError):
        ApiError.model_validate(make_error(stack_trace="boom"))
    with pytest.raises(ValidationError):
        RecoveryHint.model_validate({"action": "retry", "owner": "client", "extra": 1})
    with pytest.raises(ValidationError):
        Progress.model_validate({"unit": "pages", "completed": 1, "extra": 1})
    with pytest.raises(ValidationError):
        ProcessingData[Payload].model_validate(processing_data(extra=1))
    with pytest.raises(ValidationError):
        QualitySummary.model_validate(quality_data(aggregate_confidence=0.5))
    with pytest.raises(ValidationError):
        GraphReference.model_validate(graph_ref_data(extra=1))


def test_generic_payload_type_is_enforced():
    with pytest.raises(ValidationError):
        PayloadResponse.validate_python(success_payload(data={"value": "not-an-int"}))
    with pytest.raises(ValidationError):
        PayloadResponse.validate_python(partial_payload(data={"value": "not-an-int"}))
    with pytest.raises(ValidationError):
        PayloadResponse.validate_python(
            processing_payload(data=processing_data(partial_result={"value": "x"}))
        )


def test_failure_response_is_not_generic():
    resp = FailureResponse(request_id="r1", message="no", errors=[ApiError.model_validate(make_error())])
    assert resp.data is None
    assert resp.job_id is None and resp.document_id is None


def test_direct_construction_enforces_invariants():
    err = ApiError.model_validate(make_error())
    with pytest.raises(ValidationError):
        SuccessResponse[Payload](request_id="r", message="m", data=Payload(value=1), errors=[err])
    with pytest.raises(ValidationError):
        PartialSuccessResponse[Payload](request_id="r", message="m", data=Payload(value=1))
    with pytest.raises(ValidationError):
        ProcessingResponse[Payload](
            request_id="r", message="m", data=ProcessingData[Payload].model_validate(processing_data())
        )
    with pytest.raises(ValidationError):
        FailureResponse(request_id="r", message="m")


@pytest.mark.parametrize("field", ["details"])
@pytest.mark.parametrize(
    "bad",
    [
        {"x": object()},
        {"x": {1, 2}},
        {"x": b"bytes"},
        {"x": (1, 2)},
        {"x": float("nan")},
        {"x": float("inf")},
        {"x": [1, object()]},
        {"x": {"y": {"z": Path("/tmp/file")}}},
        {1: "non-string-key"},
    ],
)
def test_non_json_details_rejected(field, bad):
    with pytest.raises(ValidationError):
        ApiError.model_validate(make_error(**{field: bad}))


@pytest.mark.parametrize(
    "bad",
    [{"x": object()}, {"x": {1}}, {"x": float("nan")}, {"x": {"y": [Path("a")]}}],
)
def test_non_json_meta_rejected(bad):
    with pytest.raises(ValidationError):
        PayloadResponse.validate_python(success_payload(meta=bad))


def test_json_safe_details_and_meta_accepted():
    value = {
        "s": "x",
        "i": 1,
        "f": 1.5,
        "b": True,
        "n": None,
        "l": [1, "a", None, {"k": [2.5]}],
        "o": {"nested": {"deep": False}},
    }
    err = ApiError.model_validate(make_error(details=value))
    assert err.details == value
    resp = PayloadResponse.validate_python(success_payload(meta=value))
    assert resp.meta == value
    assert json.dumps(PayloadResponse.dump_python(resp, mode="json"))


def test_details_and_meta_defaults_are_not_shared_between_instances():
    a = ApiError.model_validate(make_error())
    b = ApiError.model_validate(make_error())
    a.details["k"] = "v"
    assert b.details == {}
    r1 = PayloadResponse.validate_python(success_payload())
    r2 = PayloadResponse.validate_python(success_payload())
    r1.meta["k"] = "v"
    r1.errors.append(ApiError.model_validate(make_error()))
    assert r2.meta == {} and r2.errors == []


# ================================================= error code registry
def test_known_error_codes_registry():
    expected = {
        "INVALID_FILE",
        "UNSUPPORTED_FORMAT",
        "CORRUPT_DOCUMENT",
        "DOCUMENT_TOO_LARGE",
        "PARSE_FAILED",
        "EXTRACTION_FAILED",
        "TABLE_EXTRACTION_FAILED",
        "FIDELITY_VALIDATION_FAILED",
        "ROUTING_FAILED",
        "TIMEOUT",
        "PROVIDER_UNAVAILABLE",
        "INTERNAL_ERROR",
        "REQUEST_VALIDATION_FAILED",
        "DOCUMENT_NOT_READY",
        "DOCUMENT_UNAVAILABLE",
    }
    assert error_codes.KNOWN_ERROR_CODES == expected
    for name in expected:
        assert getattr(error_codes, name) == name


@pytest.mark.parametrize("code", sorted(error_codes.KNOWN_ERROR_CODES))
def test_every_known_code_is_a_valid_api_error_code(code):
    assert ApiError.model_validate(make_error(code=code)).code == code


def test_error_code_registry_is_not_a_public_enum():
    import enum

    assert not any(
        isinstance(v, type) and issubclass(v, enum.Enum) for v in vars(error_codes).values()
    )
    assert isinstance(error_codes.KNOWN_ERROR_CODES, frozenset)
