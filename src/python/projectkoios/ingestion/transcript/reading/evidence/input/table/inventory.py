"""Bounded table producer inventories."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from projectkoios.ingestion.transcript.reading.evidence.error import (
    ReadingEvidenceError,
)
from projectkoios.ingestion.transcript.reading.evidence.input.table.evidence import (  # noqa: E501
    ReadingTableProducerEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.limits.definition import (  # noqa: E501
    READING_EVIDENCE_LIMITS,
)
from projectkoios.ingestion.transcript.reading.evidence.limits.error import (
    ReadingEvidenceLimitError,
)


@dataclass(frozen=True, slots=True, init=False)
class ReadingTableProducerEvidenceInventory:
    """Own one unique identity-sorted bounded table collection."""

    _records: tuple[ReadingTableProducerEvidence, ...] = field(repr=True)

    def __init__(self, *records: ReadingTableProducerEvidence) -> None:
        values = tuple(records)
        if len(values) > READING_EVIDENCE_LIMITS.maximum_records:
            raise ReadingEvidenceLimitError(
                "table record count exceeds its limit"
            )
        if any(
            type(value) is not ReadingTableProducerEvidence for value in values
        ):
            raise TypeError("table inventory contains an invalid value")
        identities = tuple(value.record_id.value for value in values)
        if identities != tuple(sorted(identities)) or len(identities) != len(
            set(identities)
        ):
            raise ReadingEvidenceError(
                "table records must be unique and identity sorted"
            )
        objects = tuple(
            value.lineage.source_object_id.value for value in values
        )
        regions = tuple(value.region_id.value for value in values)
        if len(objects) != len(set(objects)):
            raise ReadingEvidenceError("table source objects must be unique")
        if len(regions) != len(set(regions)):
            raise ReadingEvidenceError("table regions must be unique")
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
                "table nested evidence exceeds its aggregate limit"
            )
        if (
            sum(
                value.lineage.artifacts.aggregate_byte_length
                for value in values
            )
            > READING_EVIDENCE_LIMITS.maximum_document_referenced_artifact_bytes
        ):
            raise ReadingEvidenceLimitError(
                "table artifacts exceed their aggregate byte limit"
            )
        object.__setattr__(self, "_records", values)

    def __iter__(self) -> Iterator[ReadingTableProducerEvidence]:
        return iter(self._records)

    def __len__(self) -> int:
        return len(self._records)

    def identity_material(self) -> list[str]:
        """Return ephemeral canonical table identity material."""
        return [value.record_id.value for value in self._records]
