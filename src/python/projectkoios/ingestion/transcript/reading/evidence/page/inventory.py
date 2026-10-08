"""Complete canonical document-page inventories."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from projectkoios.ingestion.transcript.reading.evidence.error import (
    ReadingEvidenceError,
)
from projectkoios.ingestion.transcript.reading.evidence.limits.definition import (  # noqa: E501
    READING_EVIDENCE_LIMITS,
)
from projectkoios.ingestion.transcript.reading.evidence.limits.error import (
    ReadingEvidenceLimitError,
)
from projectkoios.ingestion.transcript.reading.evidence.page.evidence import (
    ReadingEvidencePage,
)


@dataclass(frozen=True, slots=True, init=False)
class ReadingEvidencePageInventory:
    """Own complete contiguous physical-page canonical reading evidence."""

    _pages: tuple[ReadingEvidencePage, ...] = field(repr=True)

    def __init__(self, *pages: ReadingEvidencePage) -> None:
        values = tuple(pages)
        if not values:
            raise ReadingEvidenceError(
                "reading page inventory must not be empty"
            )
        if len(values) > READING_EVIDENCE_LIMITS.maximum_pages:
            raise ReadingEvidenceLimitError(
                "reading page count exceeds its limit"
            )
        if any(type(value) is not ReadingEvidencePage for value in values):
            raise TypeError("reading page inventory contains an invalid value")
        indexes = tuple(
            value.page_location.physical_page_index for value in values
        )
        if indexes != tuple(range(len(values))):
            raise ReadingEvidenceError("reading pages must be contiguous")
        identities = tuple(value.page_id.value for value in values)
        if len(identities) != len(set(identities)):
            raise ReadingEvidenceError("reading pages must be unique")
        block_count = sum(len(value.blocks) for value in values)
        if block_count > READING_EVIDENCE_LIMITS.maximum_blocks:
            raise ReadingEvidenceLimitError(
                "document block count exceeds its limit"
            )
        text_bytes = sum(
            len(block.text.encode())
            for page in values
            for block in page.blocks
            if hasattr(block, "text")
        )
        if (
            text_bytes
            > READING_EVIDENCE_LIMITS.maximum_document_clean_text_bytes
        ):
            raise ReadingEvidenceLimitError(
                "document block text exceeds its limit"
            )
        object.__setattr__(self, "_pages", values)

    def __iter__(self) -> Iterator[ReadingEvidencePage]:
        return iter(self._pages)

    def __len__(self) -> int:
        return len(self._pages)

    def identity_material(self) -> list[str]:
        """Return ephemeral canonical page identity material."""
        return [value.page_id.value for value in self._pages]
