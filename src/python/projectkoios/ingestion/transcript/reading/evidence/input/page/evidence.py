"""Exact per-page text producer evidence."""

from __future__ import annotations

from dataclasses import dataclass, field

from projectkoios.ingestion.transcript.reading.evidence.identity.definition import (  # noqa: E501
    ReadingEvidenceIdentity,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.derivation import (  # noqa: E501
    ReadingEvidenceIdentityDerivation,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.kind import (
    ReadingEvidenceIdentityKind,
)
from projectkoios.ingestion.transcript.reading.evidence.limits.definition import (  # noqa: E501
    READING_EVIDENCE_LIMITS,
)
from projectkoios.ingestion.transcript.reading.evidence.status.review import (
    ReadingReviewStatus,
)
from projectkoios.ingestion.transcript.reading.evidence.stream.inventory import (  # noqa: E501
    ReadingTextStreamEvidenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.stream.selection.definition import (  # noqa: E501
    ReadingTextSelection,
)


@dataclass(frozen=True, slots=True)
class ReadingPageTextProducerEvidence:
    """Bind one page's retained streams, selection, producer, and review."""

    streams: ReadingTextStreamEvidenceInventory
    selection: ReadingTextSelection
    producer_id: ReadingEvidenceIdentity
    producer_version: str
    review_status: ReadingReviewStatus
    record_id: ReadingEvidenceIdentity = field(init=False)

    def __post_init__(self) -> None:
        if type(self.streams) is not ReadingTextStreamEvidenceInventory:
            raise TypeError(
                "streams must be ReadingTextStreamEvidenceInventory"
            )
        if type(self.selection) is not ReadingTextSelection:
            raise TypeError("selection must be ReadingTextSelection")
        self.selection.validate_against(self.streams)
        if type(self.producer_id) is not ReadingEvidenceIdentity or (
            self.producer_id.kind is not ReadingEvidenceIdentityKind.PRODUCER
        ):
            raise TypeError("producer_id must be a producer identity")
        READING_EVIDENCE_LIMITS.require_text(
            self.producer_version,
            "producer_version",
            maximum_bytes=(
                READING_EVIDENCE_LIMITS.maximum_producer_version_bytes
            ),
        )
        if not isinstance(self.review_status, ReadingReviewStatus):
            raise TypeError("review_status must be ReadingReviewStatus")
        object.__setattr__(
            self,
            "record_id",
            ReadingEvidenceIdentityDerivation.derive(
                kind=ReadingEvidenceIdentityKind.PAGE_TEXT,
                prefix="reading-page-text-producer",
                material={
                    "page_location_id": (
                        self.streams.page_location.location_id.value
                    ),
                    "stream_ids": self.streams.identity_material(),
                    "selection_id": self.selection.selection_id.value,
                    "producer_id": self.producer_id.value,
                    "producer_version": self.producer_version,
                    "review_status": self.review_status,
                },
            ),
        )
