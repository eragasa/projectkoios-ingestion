"""Typed managed-artifact verification failures."""

from __future__ import annotations

from projectkoios.ingestion.artifact.managed.limits.definition import (
    MANAGED_ARTIFACT_LIMITS,
)


class ManagedArtifactVerificationError(RuntimeError):
    """Expose one bounded stable failure code without provider exceptions."""

    def __init__(self, *, code: str, message: str) -> None:
        validated_code = MANAGED_ARTIFACT_LIMITS.require_identity_text(
            code, "verification failure code"
        )
        if type(message) is not str or not message:
            raise ValueError("verification failure message must be non-empty")
        if len(message.encode("utf-8", errors="strict")) > 4_096:
            raise ValueError("verification failure message exceeds its limit")
        super().__init__(message)
        self.code = validated_code
