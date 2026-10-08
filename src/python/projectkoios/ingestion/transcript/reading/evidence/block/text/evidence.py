"""Canonical paragraph and heading reading evidence."""

from __future__ import annotations

from dataclasses import dataclass, field

from projectkoios.ingestion.transcript.reading.evidence.block.kind import (
    ReadingEvidenceBlockKind,
)
from projectkoios.ingestion.transcript.reading.evidence.block.text.basis import (  # noqa: E501
    ReadingTextBlockProjectionBasis,
)
from projectkoios.ingestion.transcript.reading.evidence.block.text.source import (  # noqa: E501
    ReadingTextBlockSourceInventory,
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
from projectkoios.ingestion.transcript.reading.evidence.input.structure.evidence import (  # noqa: E501
    ReadingStructuredItemProducerEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.input.structure.kind import (  # noqa: E501
    ReadingStructuredItemKind,
)
from projectkoios.ingestion.transcript.reading.evidence.limits.definition import (  # noqa: E501
    READING_EVIDENCE_LIMITS,
)
from projectkoios.ingestion.transcript.reading.evidence.page.location import (
    ReadingPageLocation,
)


@dataclass(frozen=True, slots=True)
class ReadingTextEvidenceBlock:
    """Derive one ordered paragraph or heading from exact producer evidence."""

    structured_item: ReadingStructuredItemProducerEvidence
    sources: ReadingTextBlockSourceInventory
    basis: ReadingTextBlockProjectionBasis
    text: str = field(init=False)
    kind: ReadingEvidenceBlockKind = field(init=False)
    block_id: ReadingEvidenceIdentity = field(init=False)

    def __post_init__(self) -> None:
        if (
            type(self.structured_item)
            is not ReadingStructuredItemProducerEvidence
        ):
            raise TypeError(
                "structured_item must be ReadingStructuredItemProducerEvidence"
            )
        kind_by_source = {
            ReadingStructuredItemKind.PARAGRAPH: (
                ReadingEvidenceBlockKind.PARAGRAPH
            ),
            ReadingStructuredItemKind.HEADING: (
                ReadingEvidenceBlockKind.HEADING
            ),
        }
        if self.structured_item.kind not in kind_by_source:
            raise ReadingEvidenceError(
                "text block requires a text structured item"
            )
        if type(self.sources) is not ReadingTextBlockSourceInventory:
            raise TypeError("sources must be ReadingTextBlockSourceInventory")
        if not isinstance(self.basis, ReadingTextBlockProjectionBasis):
            raise TypeError("basis must be ReadingTextBlockProjectionBasis")
        source_values = tuple(self.sources)
        source_block_ids = tuple(
            value.source_block_id for value in source_values
        )
        if source_block_ids != tuple(self.structured_item.source_block_ids):
            raise ReadingEvidenceError(
                "text sources differ from structured source-block order"
            )
        if any(
            value.page_location != self.structured_item.page_location
            for value in source_values
        ):
            raise ReadingEvidenceError("text sources bind a different page")
        text = "\n".join(value.clean_text for value in source_values)
        READING_EVIDENCE_LIMITS.require_text(
            text,
            "text block",
            maximum_bytes=READING_EVIDENCE_LIMITS.maximum_block_text_bytes,
        )
        kind = kind_by_source[self.structured_item.kind]
        object.__setattr__(self, "text", text)
        object.__setattr__(self, "kind", kind)
        object.__setattr__(
            self,
            "block_id",
            ReadingEvidenceIdentityDerivation.derive(
                kind=ReadingEvidenceIdentityKind.BLOCK,
                prefix="reading-text-block",
                material={
                    "structured_item_id": self.structured_item.record_id.value,
                    "source_ids": self.sources.identity_material(),
                    "basis": self.basis,
                    "kind": kind,
                    "text": text,
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
