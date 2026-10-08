"""Typed bounded reading evidence identity values."""

from __future__ import annotations

import re
from dataclasses import dataclass

from projectkoios.ingestion.transcript.reading.evidence.error import (
    ReadingEvidenceError,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.kind import (
    ReadingEvidenceIdentityKind,
)
from projectkoios.ingestion.transcript.reading.evidence.limits.definition import (  # noqa: E501
    READING_EVIDENCE_LIMITS,
)

_IDENTITY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]*")


@dataclass(frozen=True, slots=True)
class ReadingEvidenceIdentity:
    """Bind one syntax-valid identity to its exact semantic role."""

    kind: ReadingEvidenceIdentityKind
    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ReadingEvidenceIdentityKind):
            raise TypeError("kind must be ReadingEvidenceIdentityKind")
        value = READING_EVIDENCE_LIMITS.require_text(
            self.value,
            "identity value",
            maximum_bytes=READING_EVIDENCE_LIMITS.maximum_identity_characters,
        )
        if _IDENTITY.fullmatch(value) is None:
            raise ReadingEvidenceError("identity value has invalid syntax")
