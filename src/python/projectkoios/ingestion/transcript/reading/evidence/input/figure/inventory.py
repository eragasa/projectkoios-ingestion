"""Bounded figure producer inventories."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from projectkoios.ingestion.transcript.reading.evidence.error import (
    ReadingEvidenceError,
)
from projectkoios.ingestion.transcript.reading.evidence.input.figure.evidence import (  # noqa: E501
    ReadingFigureProducerEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.limits.definition import (  # noqa: E501
    READING_EVIDENCE_LIMITS,
)
from projectkoios.ingestion.transcript.reading.evidence.limits.error import (
    ReadingEvidenceLimitError,
)


@dataclass(frozen=True, slots=True, init=False)
class ReadingFigureProducerEvidenceInventory:
    """Own one unique identity-sorted bounded figure collection."""

    _records: tuple[ReadingFigureProducerEvidence, ...] = field(repr=True)

    def __init__(self, *records: ReadingFigureProducerEvidence) -> None:
        values = tuple(records)
        if len(values) > READING_EVIDENCE_LIMITS.maximum_records:
            raise ReadingEvidenceLimitError(
                "figure record count exceeds its limit"
            )
        if any(
            type(value) is not ReadingFigureProducerEvidence for value in values
        ):
            raise TypeError("figure inventory contains an invalid value")
        identities = tuple(value.record_id.value for value in values)
        if identities != tuple(sorted(identities)) or len(identities) != len(
            set(identities)
        ):
            raise ReadingEvidenceError(
                "figure records must be unique and identity sorted"
            )
        objects = tuple(
            value.lineage.source_object_id.value for value in values
        )
        if len(objects) != len(set(objects)):
            raise ReadingEvidenceError("figure source objects must be unique")
        nested_counts = (
            sum(len(value.lineage.source_spans) for value in values),
            sum(len(value.assessment.associations) for value in values),
            sum(len(value.lineage.artifacts) for value in values),
        )
        if any(
            count > READING_EVIDENCE_LIMITS.maximum_records
            for count in nested_counts
        ):
            raise ReadingEvidenceLimitError(
                "figure nested evidence exceeds its aggregate limit"
            )
        if (
            sum(
                value.lineage.artifacts.aggregate_byte_length
                for value in values
            )
            > READING_EVIDENCE_LIMITS.maximum_document_referenced_artifact_bytes
        ):
            raise ReadingEvidenceLimitError(
                "figure artifacts exceed their aggregate byte limit"
            )
        object.__setattr__(self, "_records", values)

    def __iter__(self) -> Iterator[ReadingFigureProducerEvidence]:
        return iter(self._records)

    def __len__(self) -> int:
        return len(self._records)

    def identity_material(self) -> list[str]:
        """Return ephemeral canonical figure identity material."""
        return [value.record_id.value for value in self._records]
