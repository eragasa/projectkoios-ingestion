"""Canonical ordered figure reading evidence."""

from __future__ import annotations

from dataclasses import dataclass, field

from projectkoios.ingestion.transcript.reading.evidence.block.kind import (
    ReadingEvidenceBlockKind,
)
from projectkoios.ingestion.transcript.reading.evidence.caption.evidence import (  # noqa: E501
    ReadingCaptionEvidence,
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
from projectkoios.ingestion.transcript.reading.evidence.identity.kind import (
    ReadingEvidenceIdentityKind,
)
from projectkoios.ingestion.transcript.reading.evidence.input.figure.evidence import (  # noqa: E501
    ReadingFigureProducerEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.input.structure.evidence import (  # noqa: E501
    ReadingStructuredItemProducerEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.input.structure.kind import (  # noqa: E501
    ReadingStructuredItemKind,
)
from projectkoios.ingestion.transcript.reading.evidence.page.location import (
    ReadingPageLocation,
)


@dataclass(frozen=True, slots=True)
class ReadingFigureEvidenceBlock:
    """Bind structured figure order to exact producer and caption evidence."""

    structured_item: ReadingStructuredItemProducerEvidence
    producer_evidence: ReadingFigureProducerEvidence
    caption: ReadingCaptionEvidence | None
    kind: ReadingEvidenceBlockKind = field(
        default=ReadingEvidenceBlockKind.FIGURE, init=False
    )
    block_id: ReadingEvidenceIdentity = field(init=False)

    def __post_init__(self) -> None:
        if (
            type(self.structured_item)
            is not ReadingStructuredItemProducerEvidence
        ):
            raise TypeError("structured_item has an unsupported type")
        if self.structured_item.kind is not ReadingStructuredItemKind.FIGURE:
            raise ReadingEvidenceError("figure block requires a figure item")
        if type(self.producer_evidence) is not ReadingFigureProducerEvidence:
            raise TypeError(
                "producer_evidence must be figure producer evidence"
            )
        if (
            self.structured_item.source_object_id
            != self.producer_evidence.lineage.source_object_id
            or self.structured_item.page_location
            != self.producer_evidence.lineage.page_location
        ):
            raise ReadingEvidenceError("figure join keys are inconsistent")
        if (
            self.caption is not None
            and type(self.caption) is not ReadingCaptionEvidence
        ):
            raise TypeError("caption must be ReadingCaptionEvidence")
        association_ids = {
            value.association_id
            for value in self.producer_evidence.assessment.associations
        }
        if self.caption is not None and any(
            value not in association_ids
            for value in self.caption.association_ids
        ):
            raise ReadingEvidenceError(
                "caption is not bound to figure associations"
            )
        object.__setattr__(
            self,
            "block_id",
            ReadingEvidenceIdentityDerivation.derive(
                kind=ReadingEvidenceIdentityKind.BLOCK,
                prefix="reading-figure-block",
                material={
                    "structured_item_id": self.structured_item.record_id.value,
                    "producer_record_id": (
                        self.producer_evidence.record_id.value
                    ),
                    "caption_id": None
                    if self.caption is None
                    else self.caption.caption_id.value,
                },
            ),
        )

    @property
    def page_location(self) -> ReadingPageLocation:
        """Return the exact containing page location."""
        return self.structured_item.page_location

    @property
    def order_index(self) -> int:
        """Return the exact structured reading order."""
        return self.structured_item.order_index
