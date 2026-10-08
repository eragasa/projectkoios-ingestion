"""Immutable resource ceilings owned by canonical reading evidence."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from projectkoios.ingestion.sha256.hash import SHA256Hash
from projectkoios.ingestion.transcript.reading.evidence.error import (
    ReadingEvidenceError,
)
from projectkoios.ingestion.transcript.reading.evidence.limits.error import (
    ReadingEvidenceLimitError,
)


@dataclass(frozen=True, slots=True)
class ReadingEvidenceLimits:
    """Own fixed value, collection, and identity-input bounds."""

    maximum_identity_characters: int = field(default=512, init=False)
    maximum_string_bytes: int = field(default=16_384, init=False)
    maximum_title_bytes: int = field(default=16_384, init=False)
    maximum_label_bytes: int = field(default=4_096, init=False)
    maximum_producer_version_bytes: int = field(default=1_024, init=False)
    maximum_rule_id_bytes: int = field(default=1_024, init=False)
    maximum_page_text_bytes: int = field(default=2_000_000, init=False)
    maximum_block_text_bytes: int = field(default=262_144, init=False)
    maximum_document_text_bytes: int = field(
        default=1_073_741_824,
        init=False,
    )
    maximum_document_clean_text_bytes: int = field(
        default=1_073_741_824,
        init=False,
    )
    maximum_document_referenced_artifact_bytes: int = field(
        default=1_000_000_000_000,
        init=False,
    )
    maximum_identity_input_bytes: int = field(default=1_048_576, init=False)
    maximum_pages: int = field(default=20_000, init=False)
    maximum_streams_per_page: int = field(default=2, init=False)
    maximum_blocks: int = field(default=1_000_000, init=False)
    maximum_records: int = field(default=1_000_000, init=False)
    maximum_references: int = field(default=1_000_000, init=False)
    maximum_limitations: int = field(default=100_000, init=False)
    maximum_single_record_bytes: int = field(default=4_194_304, init=False)
    maximum_aggregate_characters: int = field(
        default=1_000_000_000,
        init=False,
    )
    maximum_total_projection_work: int = field(
        default=5_000_000,
        init=False,
    )
    maximum_source_spans: int = field(default=256, init=False)
    maximum_labels: int = field(default=256, init=False)
    maximum_associations: int = field(default=256, init=False)
    maximum_transformations: int = field(default=1_024, init=False)
    maximum_total_transformations: int = field(default=1_000_000, init=False)
    maximum_identities: int = field(default=16_384, init=False)

    def require_text(
        self,
        value: object,
        name: str,
        *,
        maximum_bytes: int | None = None,
    ) -> str:
        """Return one nonempty strictly encoded bounded string."""
        if type(value) is not str or not value:
            raise ReadingEvidenceError(f"{name} must be a non-empty string")
        try:
            encoded = value.encode("utf-8", errors="strict")
        except UnicodeEncodeError as error:
            raise ReadingEvidenceError(f"{name} must be valid UTF-8") from error
        limit = (
            self.maximum_string_bytes
            if maximum_bytes is None
            else maximum_bytes
        )
        if len(encoded) > limit:
            raise ReadingEvidenceLimitError(f"{name} exceeds its limit")
        return value

    def require_string(
        self,
        value: object,
        name: str,
        *,
        maximum_bytes: int | None = None,
    ) -> str:
        """Return one possibly empty strictly encoded bounded string."""
        if type(value) is not str:
            raise ReadingEvidenceError(f"{name} must be a built-in string")
        try:
            encoded = value.encode("utf-8", errors="strict")
        except UnicodeEncodeError as error:
            raise ReadingEvidenceError(f"{name} must be valid UTF-8") from error
        limit = (
            self.maximum_string_bytes
            if maximum_bytes is None
            else maximum_bytes
        )
        if len(encoded) > limit:
            raise ReadingEvidenceLimitError(f"{name} exceeds its limit")
        return value

    def require_optional_text(
        self,
        value: object,
        name: str,
        *,
        maximum_bytes: int | None = None,
    ) -> str | None:
        """Return one optional bounded string."""
        if value is None:
            return None
        return self.require_text(value, name, maximum_bytes=maximum_bytes)

    def require_nonnegative_int(self, value: object, name: str) -> int:
        """Return one nonnegative built-in integer."""
        if type(value) is not int or value < 0:
            raise ReadingEvidenceError(
                f"{name} must be a non-negative built-in integer"
            )
        return value

    def require_positive_int(self, value: object, name: str) -> int:
        """Return one positive built-in integer."""
        if type(value) is not int or value < 1:
            raise ReadingEvidenceError(
                f"{name} must be a positive built-in integer"
            )
        return value

    def require_confidence(self, value: object, name: str) -> float:
        """Return one finite built-in unit-interval float."""
        if type(value) is not float or not math.isfinite(value):
            raise ReadingEvidenceError(
                f"{name} must be a finite built-in float"
            )
        if not 0.0 <= value <= 1.0:
            raise ReadingEvidenceError(
                f"{name} must be in the closed unit interval"
            )
        return value

    def require_sha256(self, value: object, name: str) -> SHA256Hash:
        """Return one canonical lowercase SHA-256 value."""
        if not SHA256Hash.is_canonical(value):
            raise ReadingEvidenceError(
                f"{name} must be a canonical SHA-256 digest"
            )
        return SHA256Hash(str(value))


READING_EVIDENCE_LIMITS = ReadingEvidenceLimits()
