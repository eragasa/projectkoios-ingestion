"""Closed failures for exact typed publication loading."""

from __future__ import annotations

from enum import StrEnum


class PageProjectionPublicationLoadFailureReason(StrEnum):
    """Classify typed-load failures without exposing private paths."""

    INVALID_REQUEST = "invalid_request"
    RECEIPT_UNAVAILABLE = "receipt_unavailable"
    RECEIPT_INTEGRITY_INVALID = "receipt_integrity_invalid"
    PAYLOAD_UNAVAILABLE = "payload_unavailable"
    PAYLOAD_INTEGRITY_INVALID = "payload_integrity_invalid"
    UNSUPPORTED_SCHEMA = "unsupported_schema"
    PROJECTION_VALIDATION_FAILED = "projection_validation_failed"
    UNEXPECTED = "unexpected"


class PageProjectionPublicationLoadError(RuntimeError):
    """Report one sanitized closed typed-load failure."""

    def __init__(
        self,
        *,
        reason: PageProjectionPublicationLoadFailureReason,
        message: str,
    ) -> None:
        if not isinstance(reason, PageProjectionPublicationLoadFailureReason):
            raise TypeError("reason must be a typed-load failure reason")
        if type(message) is not str or not message:
            raise ValueError("message must be non-empty")
        if len(message.encode("utf-8", errors="strict")) > 512:
            raise ValueError("message exceeds its limit")
        self.reason = reason
        super().__init__(message)
