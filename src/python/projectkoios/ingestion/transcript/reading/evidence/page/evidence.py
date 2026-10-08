"""Complete canonical reading evidence pages."""

from __future__ import annotations

from dataclasses import dataclass, field

from projectkoios.ingestion.transcript.reading.evidence.block.inventory import (
    ReadingEvidenceBlockInventory,
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
from projectkoios.ingestion.transcript.reading.evidence.input.page.evidence import (  # noqa: E501
    ReadingPageTextProducerEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.page.location import (
    ReadingPageLocation,
)


@dataclass(frozen=True, slots=True)
class ReadingEvidencePage:
    """Bind one page's streams and selection to complete ordered blocks."""

    page_text: ReadingPageTextProducerEvidence
    blocks: ReadingEvidenceBlockInventory
    page_id: ReadingEvidenceIdentity = field(init=False)

    def __post_init__(self) -> None:
        if type(self.page_text) is not ReadingPageTextProducerEvidence:
            raise TypeError("page_text must be ReadingPageTextProducerEvidence")
        if type(self.blocks) is not ReadingEvidenceBlockInventory:
            raise TypeError("blocks must be ReadingEvidenceBlockInventory")
        location = self.page_text.streams.page_location
        if any(value.page_location != location for value in self.blocks):
            raise ReadingEvidenceError("page blocks bind a different page")
        object.__setattr__(
            self,
            "page_id",
            ReadingEvidenceIdentityDerivation.derive(
                kind=ReadingEvidenceIdentityKind.EVIDENCE_PAGE,
                prefix="reading-evidence-page",
                material={
                    "page_text_id": self.page_text.record_id.value,
                    "block_ids": self.blocks.identity_material(),
                },
            ),
        )

    @property
    def page_location(self) -> ReadingPageLocation:
        """Return the exact page location."""
        return self.page_text.streams.page_location
