"""Complete page-text producer inventories."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from projectkoios.ingestion.transcript.reading.evidence.error import (
    ReadingEvidenceError,
)
from projectkoios.ingestion.transcript.reading.evidence.input.page.evidence import (  # noqa: E501
    ReadingPageTextProducerEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.limits.definition import (  # noqa: E501
    READING_EVIDENCE_LIMITS,
)
from projectkoios.ingestion.transcript.reading.evidence.limits.error import (
    ReadingEvidenceLimitError,
)


@dataclass(frozen=True, slots=True, init=False)
class ReadingPageTextProducerEvidenceInventory:
    """Own complete contiguous physical-page text producer evidence."""

    _pages: tuple[ReadingPageTextProducerEvidence, ...] = field(repr=True)

    def __init__(self, *pages: ReadingPageTextProducerEvidence) -> None:
        values = tuple(pages)
        if not values:
            raise ReadingEvidenceError(
                "page-text producer inventory must not be empty"
            )
        if len(values) > READING_EVIDENCE_LIMITS.maximum_pages:
            raise ReadingEvidenceLimitError("page count exceeds its limit")
        if any(
            type(value) is not ReadingPageTextProducerEvidence
            for value in values
        ):
            raise TypeError("page-text inventory contains an invalid value")
        indexes = tuple(
            value.streams.page_location.physical_page_index for value in values
        )
        if indexes != tuple(range(len(values))):
            raise ReadingEvidenceError(
                "page-text inventory must have contiguous physical order"
            )
        identities = tuple(value.record_id.value for value in values)
        if len(identities) != len(set(identities)):
            raise ReadingEvidenceError(
                "page-text producer identities must be unique"
            )
        streams = tuple(stream for value in values for stream in value.streams)
        if (
            sum(len(stream.text) for stream in streams)
            > READING_EVIDENCE_LIMITS.maximum_aggregate_characters
        ):
            raise ReadingEvidenceLimitError(
                "document text streams exceed their aggregate character limit"
            )
        if (
            sum(stream.utf8_byte_length for stream in streams)
            > READING_EVIDENCE_LIMITS.maximum_document_text_bytes
        ):
            raise ReadingEvidenceLimitError(
                "document text streams exceed their aggregate byte limit"
            )
        object.__setattr__(self, "_pages", values)

    def __iter__(self) -> Iterator[ReadingPageTextProducerEvidence]:
        return iter(self._pages)

    def __len__(self) -> int:
        return len(self._pages)

    def identity_material(self) -> list[str]:
        """Return ephemeral canonical page producer identity material."""
        return [value.record_id.value for value in self._pages]
