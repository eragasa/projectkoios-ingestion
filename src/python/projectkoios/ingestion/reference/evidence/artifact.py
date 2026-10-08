"""Exact content identity for one bound reference-evidence artifact."""

from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.reference.evidence.error import (
    ReferenceEvidenceVerificationError,
)
from projectkoios.ingestion.reference.evidence.limits.definition import (
    REFERENCE_EVIDENCE_LIMITS,
)
from projectkoios.ingestion.reference.evidence.limits.error import (
    ReferenceEvidenceLimitError,
)
from projectkoios.ingestion.reference.evidence.validation import (
    REFERENCE_EVIDENCE_VALUE_REQUIREMENTS,
)
from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter


@dataclass(frozen=True, slots=True)
class ReferenceEvidenceArtifact:
    """Bind one producer artifact to exact media, digest, and byte length."""

    media_type: str
    sha256: str
    byte_length: int

    @classmethod
    def from_bytes(
        cls,
        content: bytes,
        *,
        media_type: str,
    ) -> ReferenceEvidenceArtifact:
        if not isinstance(content, bytes):
            raise TypeError("artifact content must be bytes")
        if (
            len(content)
            > REFERENCE_EVIDENCE_LIMITS.maximum_bound_artifact_bytes
        ):
            raise ReferenceEvidenceLimitError(
                "bound artifact exceeds size limit"
            )
        return cls(
            media_type=media_type,
            sha256=SHA256Fingerprinter.fingerprint(content=content),
            byte_length=len(content),
        )

    def __post_init__(self) -> None:
        REFERENCE_EVIDENCE_VALUE_REQUIREMENTS.require_text(
            self.media_type,
            "artifact media_type",
        )
        REFERENCE_EVIDENCE_VALUE_REQUIREMENTS.require_sha256(
            self.sha256,
            "artifact sha256",
        )
        REFERENCE_EVIDENCE_VALUE_REQUIREMENTS.require_nonnegative_int(
            self.byte_length,
            "artifact byte_length",
        )
        if (
            self.byte_length
            > REFERENCE_EVIDENCE_LIMITS.maximum_bound_artifact_bytes
        ):
            raise ReferenceEvidenceLimitError(
                "bound artifact exceeds size limit"
            )

    def verify(self, content: bytes, *, name: str) -> None:
        """Require exact content identity for supplied artifact bytes."""
        if not isinstance(content, bytes):
            raise TypeError(f"{name} must be bytes")
        if (
            len(content)
            > REFERENCE_EVIDENCE_LIMITS.maximum_bound_artifact_bytes
        ):
            raise ReferenceEvidenceLimitError(f"{name} exceeds size limit")
        actual = SHA256Fingerprinter.fingerprint(content=content)
        if len(content) != self.byte_length or actual != self.sha256:
            raise ReferenceEvidenceVerificationError(
                f"{name} does not match its recorded content identity"
            )
