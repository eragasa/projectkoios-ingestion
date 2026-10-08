"""Closed semantic reading-evidence storage record kinds."""

from enum import StrEnum

from projectkoios.ingestion.storage.transcript.reading.evidence.projection.collection import (  # noqa: E501
    ReadingEvidenceStorageCollection,
)


class ReadingEvidenceStorageRecordKind(StrEnum):
    """Identify one exact semantic member of the current storage schema."""

    DOCUMENT = "document"
    PAGE = "page"
    BLOCK = "block"
    CLEAN_TEXT_PRODUCER = "clean_text_producer"
    FIGURE_PRODUCER = "figure_producer"
    TABLE_PRODUCER = "table_producer"
    EQUATION_PRODUCER = "equation_producer"
    MANAGED_REFERENCE = "managed_reference"
    LIMITATION = "limitation"
    COMPLETION = "completion"

    @property
    def collection(self) -> ReadingEvidenceStorageCollection:
        """Return the sole logical collection owning this kind."""
        if self is self.DOCUMENT:
            return ReadingEvidenceStorageCollection.DOCUMENTS
        if self is self.PAGE:
            return ReadingEvidenceStorageCollection.PAGES
        if self is self.BLOCK:
            return ReadingEvidenceStorageCollection.BLOCKS
        if self in (
            self.CLEAN_TEXT_PRODUCER,
            self.FIGURE_PRODUCER,
            self.TABLE_PRODUCER,
            self.EQUATION_PRODUCER,
        ):
            return ReadingEvidenceStorageCollection.PRODUCERS
        if self is self.MANAGED_REFERENCE:
            return ReadingEvidenceStorageCollection.REFERENCES
        if self is self.LIMITATION:
            return ReadingEvidenceStorageCollection.LIMITATIONS
        return ReadingEvidenceStorageCollection.COMPLETIONS
