"""Closed sanitized failures for page-projection publication."""

from __future__ import annotations

from enum import StrEnum


class PageProjectionPublicationFailureReason(StrEnum):
    """Transport-mappable owner failure reasons without private detail."""

    INVALID_REQUEST = "invalid_request"
    UNSUPPORTED_MEDIA = "unsupported_media"
    UNSUPPORTED_PROFILE = "unsupported_profile"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    STALE_CURRENT_PUBLICATION = "stale_current_publication"
    SOURCE_BINDING_UNAVAILABLE = "source_binding_unavailable"
    SOURCE_UNAVAILABLE = "source_unavailable"
    SOURCE_BYTES_DIFFER = "source_bytes_differ"
    DEPENDENCY_UNAVAILABLE = "dependency_unavailable"
    DEPENDENCY_VERSION_DIFFERS = "dependency_version_differs"
    RESOURCE_LIMIT_EXCEEDED = "resource_limit_exceeded"
    PROJECTION_VALIDATION_FAILED = "projection_validation_failed"
    PUBLICATION_COLLISION = "publication_collision"
    PUBLICATION_INTEGRITY_INVALID = "publication_integrity_invalid"
    PUBLICATION_STORE_UNAVAILABLE = "publication_store_unavailable"
    UNEXPECTED = "unexpected"


class PageProjectionPublicationError(RuntimeError):
    """Expose exactly one closed sanitized owner failure seam."""

    __slots__ = ("reason",)

    def __init__(
        self,
        *,
        reason: PageProjectionPublicationFailureReason,
        message: str,
    ) -> None:
        if not isinstance(reason, PageProjectionPublicationFailureReason):
            raise TypeError("reason must be a publication failure reason")
        if type(message) is not str or not message:
            raise ValueError("publication failure message must be non-empty")
        if len(message.encode("utf-8", errors="strict")) > 512:
            raise ValueError("publication failure message exceeds its limit")
        self.reason = reason
        super().__init__(message)
