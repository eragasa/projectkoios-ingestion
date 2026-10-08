"""Canonical ordered equation reading evidence."""

from __future__ import annotations

from dataclasses import dataclass, field

from projectkoios.ingestion.transcript.reading.evidence.block.kind import (
    ReadingEvidenceBlockKind,
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
from projectkoios.ingestion.transcript.reading.evidence.input.equation.evidence import (  # noqa: E501
    ReadingEquationProducerEvidence,
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
class ReadingEquationEvidenceBlock:
    """Bind structured equation order to exact recognition and gate evidence."""

    structured_item: ReadingStructuredItemProducerEvidence
    producer_evidence: ReadingEquationProducerEvidence
    kind: ReadingEvidenceBlockKind = field(
        default=ReadingEvidenceBlockKind.EQUATION, init=False
    )
    block_id: ReadingEvidenceIdentity = field(init=False)

    def __post_init__(self) -> None:
        if (
            type(self.structured_item)
            is not ReadingStructuredItemProducerEvidence
        ):
            raise TypeError("structured_item has an unsupported type")
        if self.structured_item.kind is not ReadingStructuredItemKind.EQUATION:
            raise ReadingEvidenceError(
                "equation block requires an equation item"
            )
        if type(self.producer_evidence) is not ReadingEquationProducerEvidence:
            raise TypeError(
                "producer_evidence must be equation producer evidence"
            )
        if (
            self.structured_item.source_object_id
            != self.producer_evidence.lineage.source_object_id
            or self.structured_item.page_location
            != self.producer_evidence.lineage.page_location
        ):
            raise ReadingEvidenceError("equation join keys are inconsistent")
        object.__setattr__(
            self,
            "block_id",
            ReadingEvidenceIdentityDerivation.derive(
                kind=ReadingEvidenceIdentityKind.BLOCK,
                prefix="reading-equation-block",
                material={
                    "structured_item_id": self.structured_item.record_id.value,
                    "producer_record_id": (
                        self.producer_evidence.record_id.value
                    ),
                    "gate": self.producer_evidence.gate,
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
