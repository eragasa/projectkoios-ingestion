"""Immutable source-byte identity for reference evidence."""

from dataclasses import dataclass

from projectkoios.ingestion.reference.evidence.validation import (
    REFERENCE_EVIDENCE_VALUE_REQUIREMENTS,
)


@dataclass(frozen=True, slots=True)
class ReferenceEvidenceSource:
    """Identify one exact source blob without exposing its locator."""

    blob_id: str
    hash_algorithm: str
    content_sha256: str
    byte_length: int
    media_type: str

    def __post_init__(self) -> None:
        requirements = REFERENCE_EVIDENCE_VALUE_REQUIREMENTS
        requirements.require_text(
            self.blob_id,
            "source blob_id",
        )
        if self.hash_algorithm != "sha256":
            raise ValueError("only sha256 source identity is supported")
        requirements.require_sha256(
            self.content_sha256,
            "source content_sha256",
        )
        if self.blob_id != f"blob:sha256:{self.content_sha256}":
            raise ValueError("source blob_id does not match content_sha256")
        requirements.require_nonnegative_int(
            self.byte_length,
            "source byte_length",
        )
        requirements.require_text(
            self.media_type,
            "source media_type",
        )
