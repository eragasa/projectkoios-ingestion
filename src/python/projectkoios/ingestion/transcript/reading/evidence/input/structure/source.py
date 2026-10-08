"""Declared-order source-block identity inventories."""

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
class ReadingSourceBlockIdentityInventory:
    """Own one unique bounded source-block sequence in producer order."""

    _identities: tuple[ReadingEvidenceIdentity, ...] = field(repr=True)

    def __init__(self, *identities: ReadingEvidenceIdentity) -> None:
        values = tuple(identities)
        if len(values) > READING_EVIDENCE_LIMITS.maximum_identities:
            raise ReadingEvidenceLimitError(
                "source-block identity count exceeds its limit"
            )
        if any(
            type(value) is not ReadingEvidenceIdentity
            or value.kind is not ReadingEvidenceIdentityKind.SOURCE_BLOCK
            for value in values
        ):
            raise TypeError(
                "source-block inventory contains an invalid identity"
            )
        identity_values = tuple(value.value for value in values)
        if len(identity_values) != len(set(identity_values)):
            raise ReadingEvidenceError("source-block identities must be unique")
        object.__setattr__(self, "_identities", values)

    def __bool__(self) -> bool:
        return bool(self._identities)

    def __iter__(self) -> Iterator[ReadingEvidenceIdentity]:
        return iter(self._identities)

    def __len__(self) -> int:
        return len(self._identities)

    def identity_material(self) -> list[str]:
        """Return ephemeral canonical source-block identity material."""
        return [value.value for value in self._identities]
