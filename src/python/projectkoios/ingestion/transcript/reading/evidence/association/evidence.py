"""Typed reading association evidence."""

from __future__ import annotations

from dataclasses import dataclass, field

from projectkoios.ingestion.transcript.reading.evidence.association.role import (  # noqa: E501
    ReadingAssociationRole,
)
from projectkoios.ingestion.transcript.reading.evidence.error import (
    ReadingEvidenceError,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.definition import (  # noqa: E501
    ReadingEvidenceIdentity,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.derivation import (  # noqa: E501
    ReadingEvidenceIdentityDerivation,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.inventory import (  # noqa: E501
    ReadingEvidenceIdentityInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.kind import (
    ReadingEvidenceIdentityKind,
)
from projectkoios.ingestion.transcript.reading.evidence.limits.definition import (  # noqa: E501
    READING_EVIDENCE_LIMITS,
)
from projectkoios.ingestion.transcript.reading.evidence.span.inventory import (
    ReadingSourceSpanEvidenceInventory,
)


@dataclass(frozen=True, slots=True)
class ReadingAssociationEvidence:
    """Bind one visual item to exact typed source-text evidence."""

    role: ReadingAssociationRole
    text: str
    source_block_ids: ReadingEvidenceIdentityInventory
    source_spans: ReadingSourceSpanEvidenceInventory
    producer_association_id: ReadingEvidenceIdentity
    association_id: ReadingEvidenceIdentity = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.role, ReadingAssociationRole):
            raise TypeError("role must be ReadingAssociationRole")
        READING_EVIDENCE_LIMITS.require_text(
            self.text,
            "association text",
            maximum_bytes=READING_EVIDENCE_LIMITS.maximum_block_text_bytes,
        )
        if type(self.source_block_ids) is not ReadingEvidenceIdentityInventory:
            raise TypeError("source_block_ids must be an identity inventory")
        if (
            self.source_block_ids.kind
            is not ReadingEvidenceIdentityKind.SOURCE_BLOCK
            or not self.source_block_ids
        ):
            raise ReadingEvidenceError(
                "association requires source-block evidence"
            )
        if type(self.source_spans) is not ReadingSourceSpanEvidenceInventory:
            raise TypeError("source_spans must be a source-span inventory")
        if not self.source_spans:
            raise ReadingEvidenceError(
                "association requires source-span evidence"
            )
        if type(
            self.producer_association_id
        ) is not ReadingEvidenceIdentity or (
            self.producer_association_id.kind
            is not ReadingEvidenceIdentityKind.ASSOCIATION
        ):
            raise TypeError(
                "producer_association_id must be an association identity"
            )
        object.__setattr__(
            self,
            "association_id",
            ReadingEvidenceIdentityDerivation.derive(
                kind=ReadingEvidenceIdentityKind.ASSOCIATION,
                prefix="reading-association",
                material={
                    "role": self.role,
                    "text": self.text,
                    "source_block_ids": (
                        self.source_block_ids.identity_material()
                    ),
                    "source_spans": self.source_spans.identity_material(),
                    "producer_association_id": (
                        self.producer_association_id.value
                    ),
                },
            ),
        )
