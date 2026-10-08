"""Exact canonical caption evidence."""

from __future__ import annotations

from dataclasses import dataclass, field

from projectkoios.ingestion.transcript.reading.evidence.caption.basis import (
    ReadingCaptionSelectionBasis,
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


@dataclass(frozen=True, slots=True)
class ReadingCaptionEvidence:
    """Bind one normalized unique caption to exact association evidence."""

    text: str
    association_ids: ReadingEvidenceIdentityInventory
    basis: ReadingCaptionSelectionBasis
    caption_id: ReadingEvidenceIdentity = field(init=False)

    def __post_init__(self) -> None:
        text = READING_EVIDENCE_LIMITS.require_text(
            self.text,
            "caption text",
            maximum_bytes=READING_EVIDENCE_LIMITS.maximum_block_text_bytes,
        )
        if type(
            self.association_ids
        ) is not ReadingEvidenceIdentityInventory or (
            self.association_ids.kind
            is not ReadingEvidenceIdentityKind.ASSOCIATION
            or not self.association_ids
        ):
            raise TypeError(
                "association_ids must be a nonempty association inventory"
            )
        if not isinstance(self.basis, ReadingCaptionSelectionBasis):
            raise TypeError("basis must be ReadingCaptionSelectionBasis")
        object.__setattr__(
            self,
            "caption_id",
            ReadingEvidenceIdentityDerivation.derive(
                kind=ReadingEvidenceIdentityKind.CAPTION,
                prefix="reading-caption",
                material={
                    "text": text,
                    "association_ids": self.association_ids.identity_material(),
                    "basis": self.basis,
                },
            ),
        )
