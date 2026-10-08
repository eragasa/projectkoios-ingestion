"""Affected-identity inventories for canonical reading limitations."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from projectkoios.ingestion.transcript.reading.evidence.error import (
    ReadingEvidenceError,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.definition import (  # noqa: E501
    ReadingEvidenceIdentity,
)
from projectkoios.ingestion.transcript.reading.evidence.limits.definition import (  # noqa: E501
    READING_EVIDENCE_LIMITS,
)
from projectkoios.ingestion.transcript.reading.evidence.limits.error import (
    ReadingEvidenceLimitError,
)


@dataclass(frozen=True, slots=True, init=False)
class ReadingAffectedEvidenceIdentityInventory:
    """Own one sorted unique bounded heterogeneous affected-identity set."""

    _identities: tuple[ReadingEvidenceIdentity, ...] = field(repr=True)

    def __init__(self, *identities: ReadingEvidenceIdentity) -> None:
        values = tuple(identities)
        if not values:
            raise ReadingEvidenceError(
                "limitation requires affected identities"
            )
        if len(values) > READING_EVIDENCE_LIMITS.maximum_identities:
            raise ReadingEvidenceLimitError(
                "affected identity count exceeds its limit"
            )
        if any(type(value) is not ReadingEvidenceIdentity for value in values):
            raise TypeError(
                "affected identity inventory contains an invalid value"
            )
        keys = tuple((value.kind.value, value.value) for value in values)
        if keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
            raise ReadingEvidenceError(
                "affected identities must be sorted and unique"
            )
        object.__setattr__(self, "_identities", values)

    def __iter__(self) -> Iterator[ReadingEvidenceIdentity]:
        return iter(self._identities)

    def __len__(self) -> int:
        return len(self._identities)

    def identity_material(self) -> list[dict[str, str]]:
        """Return ephemeral canonical affected-identity material."""
        return [
            {"kind": value.kind.value, "value": value.value}
            for value in self._identities
        ]
