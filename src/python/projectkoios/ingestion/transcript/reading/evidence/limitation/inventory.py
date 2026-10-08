"""Sorted unique canonical reading limitation inventories."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from projectkoios.ingestion.transcript.reading.evidence.error import (
    ReadingEvidenceError,
)
from projectkoios.ingestion.transcript.reading.evidence.limitation.definition import (  # noqa: E501
    ReadingEvidenceLimitation,
)
from projectkoios.ingestion.transcript.reading.evidence.limits.definition import (  # noqa: E501
    READING_EVIDENCE_LIMITS,
)
from projectkoios.ingestion.transcript.reading.evidence.limits.error import (
    ReadingEvidenceLimitError,
)


@dataclass(frozen=True, slots=True, init=False)
class ReadingEvidenceLimitationInventory:
    """Own one sorted unique bounded canonical limitation collection."""

    _limitations: tuple[ReadingEvidenceLimitation, ...] = field(repr=True)

    def __init__(self, *limitations: ReadingEvidenceLimitation) -> None:
        values = tuple(limitations)
        if len(values) > READING_EVIDENCE_LIMITS.maximum_limitations:
            raise ReadingEvidenceLimitError(
                "limitation count exceeds its limit"
            )
        if any(
            type(value) is not ReadingEvidenceLimitation for value in values
        ):
            raise TypeError("limitation inventory contains an invalid value")
        identities = tuple(value.limitation_id.value for value in values)
        if identities != tuple(sorted(identities)) or len(identities) != len(
            set(identities)
        ):
            raise ReadingEvidenceError("limitations must be sorted and unique")
        object.__setattr__(self, "_limitations", values)

    def __bool__(self) -> bool:
        return bool(self._limitations)

    def __iter__(self) -> Iterator[ReadingEvidenceLimitation]:
        return iter(self._limitations)

    def __len__(self) -> int:
        return len(self._limitations)

    def identity_material(self) -> list[str]:
        """Return ephemeral canonical limitation identity material."""
        return [value.limitation_id.value for value in self._limitations]
