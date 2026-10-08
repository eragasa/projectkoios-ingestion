"""Exact clean-text producer evidence."""

from __future__ import annotations

from dataclasses import dataclass, field

from projectkoios.ingestion.sha256.fingerprinter import SHA256Fingerprinter
from projectkoios.ingestion.sha256.hash import SHA256Hash
from projectkoios.ingestion.transcript.reading.evidence.error import (
    ReadingEvidenceError,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.definition import (  # noqa: E501
    ReadingEvidenceIdentity,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.derivation import (  # noqa: E501
    ReadingEvidenceIdentityDerivation,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.kind import (
    ReadingEvidenceIdentityKind,
)
from projectkoios.ingestion.transcript.reading.evidence.input.text.transformation.inventory import (  # noqa: E501
    ReadingTextTransformationInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.limits.definition import (  # noqa: E501
    READING_EVIDENCE_LIMITS,
)
from projectkoios.ingestion.transcript.reading.evidence.page.location import (
    ReadingPageLocation,
)


@dataclass(frozen=True, slots=True)
class ReadingCleanTextProducerEvidence:
    """Bind exact source-block raw/clean text and typed transformations."""

    selected_stream_id: ReadingEvidenceIdentity
    source_block_id: ReadingEvidenceIdentity
    page_location: ReadingPageLocation
    order_index: int
    raw_text: str
    clean_text: str
    transformations: ReadingTextTransformationInventory
    producer_id: ReadingEvidenceIdentity
    producer_version: str
    raw_text_sha256: SHA256Hash = field(init=False)
    clean_text_sha256: SHA256Hash = field(init=False)
    record_id: ReadingEvidenceIdentity = field(init=False)

    def __post_init__(self) -> None:
        roles = (
            (
                self.selected_stream_id,
                ReadingEvidenceIdentityKind.TEXT_STREAM,
                "selected_stream_id",
            ),
            (
                self.source_block_id,
                ReadingEvidenceIdentityKind.SOURCE_BLOCK,
                "source_block_id",
            ),
            (
                self.producer_id,
                ReadingEvidenceIdentityKind.PRODUCER,
                "producer_id",
            ),
        )
        for value, kind, name in roles:
            if (
                type(value) is not ReadingEvidenceIdentity
                or value.kind is not kind
            ):
                raise TypeError(f"{name} has the wrong identity role")
        if type(self.page_location) is not ReadingPageLocation:
            raise TypeError("page_location must be ReadingPageLocation")
        READING_EVIDENCE_LIMITS.require_nonnegative_int(
            self.order_index, "order_index"
        )
        raw = READING_EVIDENCE_LIMITS.require_text(
            self.raw_text,
            "raw_text",
            maximum_bytes=READING_EVIDENCE_LIMITS.maximum_block_text_bytes,
        )
        clean = READING_EVIDENCE_LIMITS.require_text(
            self.clean_text,
            "clean_text",
            maximum_bytes=READING_EVIDENCE_LIMITS.maximum_block_text_bytes,
        )
        if type(self.transformations) is not ReadingTextTransformationInventory:
            raise TypeError(
                "transformations must be ReadingTextTransformationInventory"
            )
        if self.transformations.apply(raw) != clean:
            raise ReadingEvidenceError(
                "clean text does not match exact transformations"
            )
        READING_EVIDENCE_LIMITS.require_text(
            self.producer_version,
            "producer_version",
            maximum_bytes=(
                READING_EVIDENCE_LIMITS.maximum_producer_version_bytes
            ),
        )
        raw_digest = SHA256Fingerprinter.fingerprint(content=raw.encode())
        clean_digest = SHA256Fingerprinter.fingerprint(content=clean.encode())
        object.__setattr__(self, "raw_text_sha256", raw_digest)
        object.__setattr__(self, "clean_text_sha256", clean_digest)
        object.__setattr__(
            self,
            "record_id",
            ReadingEvidenceIdentityDerivation.derive(
                kind=ReadingEvidenceIdentityKind.CLEAN_TEXT,
                prefix="reading-clean-text-producer",
                material={
                    "selected_stream_id": self.selected_stream_id.value,
                    "source_block_id": self.source_block_id.value,
                    "page_location_id": self.page_location.location_id.value,
                    "order_index": self.order_index,
                    "raw_text_sha256": raw_digest,
                    "clean_text_sha256": clean_digest,
                    "transformation_ids": (
                        self.transformations.identity_material()
                    ),
                    "producer_id": self.producer_id.value,
                    "producer_version": self.producer_version,
                },
            ),
        )
