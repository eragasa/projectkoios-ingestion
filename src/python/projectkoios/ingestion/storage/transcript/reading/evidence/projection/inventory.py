"""Canonical backend-neutral reading-evidence storage document inventories."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from projectkoios.ingestion.storage.transcript.reading.evidence.projection.document import (  # noqa: E501
    ReadingEvidenceStorageDocument,
)
from projectkoios.ingestion.storage.transcript.reading.evidence.projection.kind import (  # noqa: E501
    ReadingEvidenceStorageRecordKind,
)
from projectkoios.ingestion.transcript.reading.evidence.limits.definition import (  # noqa: E501
    READING_EVIDENCE_LIMITS,
)


@dataclass(frozen=True, slots=True, init=False)
class ReadingEvidenceStorageDocumentInventory:
    """Own canonically ordered unique storage documents for one scope."""

    _documents: tuple[ReadingEvidenceStorageDocument, ...] = field(repr=True)

    def __init__(self, *documents: ReadingEvidenceStorageDocument) -> None:
        values = tuple(documents)
        if len(values) > READING_EVIDENCE_LIMITS.maximum_records:
            raise ValueError("storage document count exceeds its limit")
        if any(
            type(value) is not ReadingEvidenceStorageDocument
            for value in values
        ):
            raise TypeError("storage inventory contains an invalid document")
        keys = tuple(
            (value.kind.collection.value, value.document_id) for value in values
        )
        if keys != tuple(sorted(keys)):
            raise ValueError("storage documents must be canonical")
        if len(keys) != len(set(keys)):
            raise ValueError("storage document identities must be unique")
        if values:
            first = values[0]
            if any(
                value.schema_version != first.schema_version
                or value.generation_id != first.generation_id
                or value.evidence_document_id != first.evidence_document_id
                for value in values[1:]
            ):
                raise ValueError("storage inventory mixes document scope")
        object.__setattr__(self, "_documents", values)

    def __iter__(self) -> Iterator[ReadingEvidenceStorageDocument]:
        return iter(self._documents)

    def __len__(self) -> int:
        return len(self._documents)

    def for_kind(
        self, kind: ReadingEvidenceStorageRecordKind
    ) -> tuple[ReadingEvidenceStorageDocument, ...]:
        """Return exact members of one semantic kind."""
        if not isinstance(kind, ReadingEvidenceStorageRecordKind):
            raise TypeError("storage record kind has an unsupported type")
        return tuple(value for value in self._documents if value.kind is kind)
