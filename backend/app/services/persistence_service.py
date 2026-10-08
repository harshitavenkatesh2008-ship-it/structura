"""Document metadata and Document Graph persistence service (Checkpoint 14).

Manages persistent storage and retrieval of:
- Document metadata (ingested documents)
- Canonical Document Graph outputs
- Structured error details and partial-success outcomes

Supports both Supabase persistence and a transparent in-memory fallback
for local development and offline testing.
"""

from typing import Any
import json
import logging

from backend.app.core import error_codes
from backend.app.models.document_graph import Document
from backend.app.models.ingestion import IngestedDocument
from backend.app.services.supabase_client import (
    SupabaseApiError,
    SupabaseClient,
    SupabaseConnectionError,
)

logger = logging.getLogger(__name__)


class PersistenceError(Exception):
    """Raised when persistence operations fail."""

    def __init__(self, message: str, code: str = error_codes.PERSISTENCE_ERROR, details: Any = None) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details


class PersistenceService:
    """Unified service for document metadata and Document Graph persistence."""

    def __init__(
        self,
        client: SupabaseClient | None = None,
        bucket: str = "documents",
    ) -> None:
        self.client = client
        self.bucket = bucket
        # Local fallback store when Supabase is unconfigured or in offline mode
        self._local_docs: dict[str, dict[str, Any]] = {}
        self._local_graphs: dict[str, str] = {}  # document_id -> raw json string
        self._local_outcomes: dict[str, dict[str, Any]] = {}  # job_id -> outcome

    @property
    def is_supabase_enabled(self) -> bool:
        return self.client is not None

    # ------------------------------------------------------- document metadata
    async def save_document_metadata(self, doc: IngestedDocument) -> dict[str, Any]:
        """Persist ingested document metadata."""
        record = doc.model_dump(mode="json")
        if not self.client:
            self._local_docs[doc.document_id] = dict(record)
            return dict(record)

        try:
            records = await self.client.insert("documents", record, upsert=True)
            return records[0] if records else record
        except (SupabaseConnectionError, SupabaseApiError) as exc:
            logger.warning("Supabase save_document_metadata failed, falling back to local: %s", exc)
            self._local_docs[doc.document_id] = dict(record)
            return dict(record)

    async def get_document_metadata(self, document_id: str) -> dict[str, Any] | None:
        """Retrieve document metadata by document_id."""
        if not self.client:
            return self._local_docs.get(document_id)

        try:
            records = await self.client.select("documents", {"document_id": f"eq.{document_id}"})
            if records:
                return records[0]
            return self._local_docs.get(document_id)
        except (SupabaseConnectionError, SupabaseApiError) as exc:
            logger.warning("Supabase get_document_metadata failed: %s", exc)
            return self._local_docs.get(document_id)

    async def has_document(self, document_id: str) -> bool:
        """Check if document metadata exists."""
        meta = await self.get_document_metadata(document_id)
        return meta is not None

    # ---------------------------------------------------------- document graph
    async def save_document_graph(
        self,
        document_id: str,
        document_graph: Document | dict[str, Any],
        job_id: str | None = None,
    ) -> str:
        """Persist a canonical Document Graph JSON output. Returns reference key."""
        if isinstance(document_graph, Document):
            raw_json = document_graph.model_dump_json(indent=2)
        else:
            raw_json = json.dumps(document_graph, indent=2)

        storage_path = f"graphs/{document_id}.json"

        if not self.client:
            self._local_graphs[document_id] = raw_json
            return f"local://{storage_path}"

        try:
            # Upload to Supabase Storage
            key = await self.client.upload_object(
                bucket=self.bucket,
                path=storage_path,
                content=raw_json.encode("utf-8"),
                content_type="application/json",
            )
            # Also store record in document_graphs table if present
            try:
                await self.client.insert(
                    "document_graphs",
                    {
                        "document_id": document_id,
                        "job_id": job_id,
                        "storage_key": key,
                    },
                    upsert=True,
                )
            except Exception:
                pass  # Storage upload succeeded, table record is secondary
            return key
        except SupabaseConnectionError as exc:
            logger.warning("Supabase storage unreachable, falling back to local: %s", exc)
            self._local_graphs[document_id] = raw_json
            return f"local://{storage_path}"
        except SupabaseApiError as exc:
            raise PersistenceError(
                f"Failed to store Document Graph: {exc.message}",
                code=error_codes.PERSISTENCE_ERROR,
                details=exc.details,
            ) from exc

    async def get_document_graph(self, document_id: str) -> Document | None:
        """Retrieve and parse a stored Document Graph by document_id."""
        raw_bytes: bytes | None = None
        storage_path = f"graphs/{document_id}.json"

        if self.client:
            try:
                raw_bytes = await self.client.get_object(self.bucket, storage_path)
            except (SupabaseConnectionError, SupabaseApiError) as exc:
                logger.warning("Supabase get_document_graph failed: %s", exc)

        if raw_bytes is None:
            # Check local store
            raw_str = self._local_graphs.get(document_id)
            if raw_str is not None:
                raw_bytes = raw_str.encode("utf-8")

        if raw_bytes is None:
            return None

        try:
            parsed = json.loads(raw_bytes.decode("utf-8"))
            return Document.model_validate(parsed)
        except Exception as exc:
            raise PersistenceError(
                f"Stored Document Graph is malformed: {exc}",
                code=error_codes.CORRUPT_DOCUMENT,
            ) from exc

    # -------------------------------------------------------- outcome & errors
    async def record_processing_outcome(
        self,
        job_id: str,
        document_id: str,
        *,
        status: str,
        error_code: str | None = None,
        error_message: str | None = None,
        partial_results: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Record structured error and partial-success details for a job."""
        record = {
            "job_id": job_id,
            "document_id": document_id,
            "status": status,
            "error_code": error_code,
            "error_message": error_message,
            "partial_results": partial_results,
        }
        self._local_outcomes[job_id] = record

        if self.client:
            try:
                await self.client.insert("job_outcomes", record, upsert=True)
            except Exception as exc:
                logger.warning("Supabase record_processing_outcome failed: %s", exc)

        return record

    async def get_processing_outcome(self, job_id: str) -> dict[str, Any] | None:
        """Fetch recorded outcome for a job."""
        if not self.client:
            return self._local_outcomes.get(job_id)

        try:
            records = await self.client.select("job_outcomes", {"job_id": f"eq.{job_id}"})
            if records:
                return records[0]
        except Exception:
            pass
        return self._local_outcomes.get(job_id)
