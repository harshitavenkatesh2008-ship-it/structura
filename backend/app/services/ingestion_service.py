"""File ingestion service (Checkpoint 9).

Validates an upload as an upload ARTIFACT only (extension, content type, size)
and stores it locally. No parsing or corruption detection happens here.

The service raises domain exceptions; it never builds HTTP responses.
Stored files are named only from a generated UUID and a whitelisted extension,
so the client filename can never influence a filesystem path.
"""

import asyncio
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import BinaryIO, Mapping, Protocol
from uuid import uuid4

from backend.app.core import error_codes
from backend.app.models.ingestion import IngestedDocument

MAX_UPLOAD_BYTES = 50 * 1024 * 1024
CHUNK_SIZE = 1024 * 1024

# <repo>/backend/app/services/ingestion_service.py -> parents[3] is the repo root.
DEFAULT_UPLOAD_ROOT = Path(__file__).resolve().parents[3] / "data" / "uploads"
STORAGE_PREFIX = "uploads"

_GENERIC_CONTENT_TYPES = frozenset({"", "application/octet-stream", "binary/octet-stream"})


@dataclass(frozen=True)
class FormatSpec:
    format: str
    content_types: tuple[str, ...]  # first entry is the canonical type


# Single source of truth: extension (no dot) -> format and accepted MIME types.
SUPPORTED_FORMATS: Mapping[str, FormatSpec] = MappingProxyType(
    {
        "pdf": FormatSpec("pdf", ("application/pdf", "application/x-pdf")),
        "xlsx": FormatSpec(
            "xlsx",
            ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",),
        ),
        "pptx": FormatSpec(
            "pptx",
            ("application/vnd.openxmlformats-officedocument.presentationml.presentation",),
        ),
        "png": FormatSpec("png", ("image/png",)),
        "jpg": FormatSpec("jpg", ("image/jpeg", "image/jpg", "image/pjpeg")),
        "jpeg": FormatSpec("jpeg", ("image/jpeg", "image/jpg", "image/pjpeg")),
        "tiff": FormatSpec("tiff", ("image/tiff", "image/x-tiff")),
    }
)


# ------------------------------------------------------------------- errors
class IngestionError(Exception):
    """Upload rejected by validation. Carries a public error code."""

    code: str = error_codes.INVALID_FILE

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class EmptyUploadError(IngestionError):
    code = error_codes.INVALID_FILE


class UnsupportedFormatError(IngestionError):
    code = error_codes.UNSUPPORTED_FORMAT


class FileTooLargeError(IngestionError):
    code = error_codes.DOCUMENT_TOO_LARGE


class IngestionStorageError(Exception):
    """Unexpected storage failure. Message is intentionally generic and safe."""


class AsyncReadable(Protocol):
    """Anything with an async read(size); Starlette's UploadFile qualifies."""

    async def read(self, size: int = -1) -> bytes: ...


# ------------------------------------------------------------------ helpers
def sanitize_filename(raw: str) -> str:
    """Return only the final path component, with non-printable characters removed.

    Used for display/metadata only; it is never used to build a storage path.
    """
    name = raw.replace("\\", "/").rsplit("/", 1)[-1]
    return "".join(ch for ch in name if ch.isprintable()).strip()


def extract_extension(filename: str) -> str:
    """Lowercase extension without the dot, or '' when there is none."""
    return PurePosixPath(sanitize_filename(filename)).suffix.lower().lstrip(".")


def _supported_details() -> dict:
    return {"supported_formats": sorted(SUPPORTED_FORMATS)}


def resolve_content_type(spec: FormatSpec, raw: str | None) -> str:
    """Accept a missing/generic type; reject a specific type that contradicts the extension."""
    normalized = (raw or "").split(";", 1)[0].strip().lower()
    if normalized in _GENERIC_CONTENT_TYPES:
        return spec.content_types[0]
    if normalized in spec.content_types:
        return normalized
    raise UnsupportedFormatError(
        "The file content type does not match the file extension.", _supported_details()
    )


# ------------------------------------------------------------------ service
class IngestionService:
    def __init__(
        self,
        upload_root: Path | None = None,
        max_bytes: int = MAX_UPLOAD_BYTES,
        chunk_size: int = CHUNK_SIZE,
    ) -> None:
        self._root = Path(upload_root) if upload_root is not None else DEFAULT_UPLOAD_ROOT
        self._max_bytes = max_bytes
        self._chunk_size = chunk_size

    async def ingest(
        self, *, filename: str, content_type: str | None, reader: AsyncReadable
    ) -> IngestedDocument:
        extension = extract_extension(filename)
        spec = SUPPORTED_FORMATS.get(extension)
        if spec is None:
            raise UnsupportedFormatError(
                "The file extension is not supported.", _supported_details()
            )
        resolved_content_type = resolve_content_type(spec, content_type)

        document_id = str(uuid4())
        final_path = self._root / f"{document_id}.{extension}"
        part_path = self._root / f"{document_id}.{extension}.part"

        try:
            self._root.mkdir(parents=True, exist_ok=True)
            size = 0
            with part_path.open("xb") as handle:
                while True:
                    chunk = await reader.read(self._chunk_size)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > self._max_bytes:
                        raise FileTooLargeError(
                            "The file exceeds the maximum upload size.",
                            {"max_bytes": self._max_bytes},
                        )
                    await asyncio.to_thread(self._write_chunk, handle, chunk)
            if size == 0:
                raise EmptyUploadError("The uploaded file is empty.")

            ingested = IngestedDocument(
                document_id=document_id,
                filename=sanitize_filename(filename),
                format=spec.format,
                content_type=resolved_content_type,
                size_bytes=size,
                storage_key=f"{STORAGE_PREFIX}/{document_id}.{extension}",
            )
            part_path.replace(final_path)  # publish only a fully written file
            return ingested
        except OSError as exc:
            self._discard(part_path)
            raise IngestionStorageError("The file could not be stored.") from exc
        except BaseException:
            # Validation errors, unexpected errors and task cancellation alike.
            self._discard(part_path)
            raise

    def has_document(self, document_id: str) -> bool:
        doc_id = (document_id or "").strip()
        if not doc_id or "/" in doc_id or "\\" in doc_id or ".." in doc_id:
            return False
        if not self._root.exists():
            return False
        for ext in SUPPORTED_FORMATS:
            candidate = self._root / f"{doc_id}.{ext}"
            if candidate.is_file():
                return True
        return False

    def _write_chunk(self, handle: BinaryIO, chunk: bytes) -> None:
        handle.write(chunk)

    @staticmethod
    def _discard(path: Path) -> None:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
