"""Semantic reading evidence identity inventories."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from projectkoios.ingestion.transcript.reading.evidence.error import (
    ReadingEvidenceError,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.definition import (  # noqa: E501
    ReadingEvidenceIdentity,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.kind import (
    ReadingEvidenceIdentityKind,
)
from projectkoios.ingestion.transcript.reading.evidence.limits.definition import (  # noqa: E501
    READING_EVIDENCE_LIMITS,
)
from projectkoios.ingestion.transcript.reading.evidence.limits.error import (
    ReadingEvidenceLimitError,
)


@dataclass(frozen=True, slots=True, init=False)
class ReadingEvidenceIdentityInventory:
    """Own one sorted, unique, role-homogeneous identity collection."""

    kind: ReadingEvidenceIdentityKind
    _identities: tuple[ReadingEvidenceIdentity, ...] = field(repr=True)

    def __init__(
        self,
        kind: ReadingEvidenceIdentityKind,
        *identities: ReadingEvidenceIdentity,
    ) -> None:
        if not isinstance(kind, ReadingEvidenceIdentityKind):
            raise TypeError("kind must be ReadingEvidenceIdentityKind")
        values = tuple(identities)
        if len(values) > READING_EVIDENCE_LIMITS.maximum_identities:
            raise ReadingEvidenceLimitError("identity count exceeds its limit")
        if any(type(value) is not ReadingEvidenceIdentity for value in values):
            raise TypeError("identity inventory contains an invalid value")
        if any(value.kind is not kind for value in values):
            raise ReadingEvidenceError(
                "identity inventory contains another role"
            )
        strings = tuple(value.value for value in values)
        if strings != tuple(sorted(strings)):
            raise ReadingEvidenceError("identities must be sorted")
        if len(strings) != len(set(strings)):
            raise ReadingEvidenceError("identities must be unique")
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "_identities", values)

    def __bool__(self) -> bool:
        return bool(self._identities)

    def __iter__(self) -> Iterator[ReadingEvidenceIdentity]:
        return iter(self._identities)

    def __len__(self) -> int:
        return len(self._identities)

    def identity_material(self) -> list[str]:
        """Return ephemeral canonical string material for owner hashing."""
        return [identity.value for identity in self._identities]
