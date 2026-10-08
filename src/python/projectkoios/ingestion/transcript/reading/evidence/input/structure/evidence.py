"""Ordered structured-item producer evidence."""

from __future__ import annotations

from dataclasses import dataclass, field

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
from projectkoios.ingestion.transcript.reading.evidence.input.structure.kind import (  # noqa: E501
    ReadingStructuredItemKind,
)
from projectkoios.ingestion.transcript.reading.evidence.input.structure.source import (  # noqa: E501
    ReadingSourceBlockIdentityInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.limits.definition import (  # noqa: E501
    READING_EVIDENCE_LIMITS,
)
from projectkoios.ingestion.transcript.reading.evidence.page.location import (
    ReadingPageLocation,
)

_TEXT_KINDS = frozenset(
    (ReadingStructuredItemKind.PARAGRAPH, ReadingStructuredItemKind.HEADING)
)


@dataclass(frozen=True, slots=True)
class ReadingStructuredItemProducerEvidence:
    """Bind one exact ordered item to text blocks or one source object."""

    page_location: ReadingPageLocation
    order_index: int
    kind: ReadingStructuredItemKind
    source_block_ids: ReadingSourceBlockIdentityInventory
    source_object_id: ReadingEvidenceIdentity | None
    producer_id: ReadingEvidenceIdentity
    producer_version: str
    record_id: ReadingEvidenceIdentity = field(init=False)

    def __post_init__(self) -> None:
        if type(self.page_location) is not ReadingPageLocation:
            raise TypeError("page_location must be ReadingPageLocation")
        READING_EVIDENCE_LIMITS.require_nonnegative_int(
            self.order_index, "order_index"
        )
        if not isinstance(self.kind, ReadingStructuredItemKind):
            raise TypeError("kind must be ReadingStructuredItemKind")
        if (
            type(self.source_block_ids)
            is not ReadingSourceBlockIdentityInventory
        ):
            raise TypeError(
                "source_block_ids must be ReadingSourceBlockIdentityInventory"
            )
        if self.kind in _TEXT_KINDS:
            if not self.source_block_ids or self.source_object_id is not None:
                raise ReadingEvidenceError(
                    "text item requires blocks and forbids a source object"
                )
        elif self.source_block_ids or (
            type(self.source_object_id) is not ReadingEvidenceIdentity
            or self.source_object_id.kind
            is not ReadingEvidenceIdentityKind.SOURCE_OBJECT
        ):
            raise ReadingEvidenceError(
                "visual item requires one object and forbids text blocks"
            )
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
        object.__setattr__(
            self,
            "record_id",
            ReadingEvidenceIdentityDerivation.derive(
                kind=ReadingEvidenceIdentityKind.STRUCTURED_ITEM,
                prefix="reading-structured-item-producer",
                material={
                    "page_location_id": self.page_location.location_id.value,
                    "order_index": self.order_index,
                    "kind": self.kind,
                    "source_block_ids": (
                        self.source_block_ids.identity_material()
                    ),
                    "source_object_id": (
                        None
                        if self.source_object_id is None
                        else self.source_object_id.value
                    ),
                    "producer_id": self.producer_id.value,
                    "producer_version": self.producer_version,
                },
            ),
        )
