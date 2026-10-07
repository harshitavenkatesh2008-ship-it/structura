"""Registry of initial known public error codes (Checkpoint 8).

These are CONVENIENCE constants only. `ApiError.code` is an open string
validated by the pattern ^[A-Z][A-Z0-9_]{0,63}$, so codes not listed here are
still valid and older clients must tolerate unknown codes.

No HTTP status mapping lives here; that belongs to a later checkpoint.
"""

# Request / input problems
INVALID_FILE = "INVALID_FILE"  # Upload is missing, empty, or unreadable as a file.
UNSUPPORTED_FORMAT = "UNSUPPORTED_FORMAT"  # File type is not supported.
CORRUPT_DOCUMENT = "CORRUPT_DOCUMENT"  # Document is damaged and cannot be opened.
DOCUMENT_TOO_LARGE = "DOCUMENT_TOO_LARGE"  # Document exceeds a size or page limit.
REQUEST_VALIDATION_FAILED = "REQUEST_VALIDATION_FAILED"  # Request body/params invalid.

# Processing
PARSE_FAILED = "PARSE_FAILED"  # Document could not be parsed.
EXTRACTION_FAILED = "EXTRACTION_FAILED"  # Content extraction failed.
TABLE_EXTRACTION_FAILED = "TABLE_EXTRACTION_FAILED"  # Table extraction failed.
ROUTING_FAILED = "ROUTING_FAILED"  # No processing route could be selected.
TIMEOUT = "TIMEOUT"  # Processing exceeded its time limit.

# Quality
FIDELITY_VALIDATION_FAILED = "FIDELITY_VALIDATION_FAILED"  # Output failed fidelity checks.

# Dependencies / availability
PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"  # An external provider is unavailable.
DOCUMENT_NOT_READY = "DOCUMENT_NOT_READY"  # Document is still being processed.
DOCUMENT_UNAVAILABLE = "DOCUMENT_UNAVAILABLE"  # Document is missing or not retrievable.

# Internal
INTERNAL_ERROR = "INTERNAL_ERROR"  # Unexpected server-side failure.

KNOWN_ERROR_CODES: frozenset[str] = frozenset(
    {
        INVALID_FILE,
        UNSUPPORTED_FORMAT,
        CORRUPT_DOCUMENT,
        DOCUMENT_TOO_LARGE,
        PARSE_FAILED,
        EXTRACTION_FAILED,
        TABLE_EXTRACTION_FAILED,
        FIDELITY_VALIDATION_FAILED,
        ROUTING_FAILED,
        TIMEOUT,
        PROVIDER_UNAVAILABLE,
        INTERNAL_ERROR,
        REQUEST_VALIDATION_FAILED,
        DOCUMENT_NOT_READY,
        DOCUMENT_UNAVAILABLE,
    }
)
