"""Declared-order association evidence inventories."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from projectkoios.ingestion.transcript.reading.evidence.association.evidence import (  # noqa: E501
    ReadingAssociationEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.error import (
    ReadingEvidenceError,
)
from projectkoios.ingestion.transcript.reading.evidence.limits.definition import (  # noqa: E501
    READING_EVIDENCE_LIMITS,
)
from projectkoios.ingestion.transcript.reading.evidence.limits.error import (
    ReadingEvidenceLimitError,
)


@dataclass(frozen=True, slots=True, init=False)
class ReadingAssociationEvidenceInventory:
    """Own one declared-order, unique, bounded association collection."""

    _associations: tuple[ReadingAssociationEvidence, ...] = field(repr=True)

    def __init__(self, *associations: ReadingAssociationEvidence) -> None:
        values = tuple(associations)
        if len(values) > READING_EVIDENCE_LIMITS.maximum_associations:
            raise ReadingEvidenceLimitError(
                "association count exceeds its limit"
            )
        if any(
            type(value) is not ReadingAssociationEvidence for value in values
        ):
            raise TypeError("association inventory contains an invalid value")
        identities = tuple(value.association_id.value for value in values)
        if len(identities) != len(set(identities)):
            raise ReadingEvidenceError("associations must be unique")
        object.__setattr__(self, "_associations", values)

    def __bool__(self) -> bool:
        return bool(self._associations)

    def __iter__(self) -> Iterator[ReadingAssociationEvidence]:
        return iter(self._associations)

    def __len__(self) -> int:
        return len(self._associations)

    def identity_material(self) -> list[str]:
        """Return ephemeral canonical association identity material."""
        return [value.association_id.value for value in self._associations]
