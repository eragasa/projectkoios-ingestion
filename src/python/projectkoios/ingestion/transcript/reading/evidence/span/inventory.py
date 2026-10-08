"""Declared-order reading source-span inventories."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from projectkoios.ingestion.transcript.reading.evidence.error import (
    ReadingEvidenceError,
)
from projectkoios.ingestion.transcript.reading.evidence.limits.definition import (  # noqa: E501
    READING_EVIDENCE_LIMITS,
)
from projectkoios.ingestion.transcript.reading.evidence.limits.error import (
    ReadingEvidenceLimitError,
)
from projectkoios.ingestion.transcript.reading.evidence.span.evidence import (
    ReadingSourceSpanEvidence,
)


@dataclass(frozen=True, slots=True, init=False)
class ReadingSourceSpanEvidenceInventory:
    """Own one declared-source-order, unique, bounded span collection."""

    _spans: tuple[ReadingSourceSpanEvidence, ...] = field(repr=True)

    def __init__(self, *spans: ReadingSourceSpanEvidence) -> None:
        values = tuple(spans)
        if len(values) > READING_EVIDENCE_LIMITS.maximum_source_spans:
            raise ReadingEvidenceLimitError(
                "source span count exceeds its limit"
            )
        if any(
            type(value) is not ReadingSourceSpanEvidence for value in values
        ):
            raise TypeError("source span inventory contains an invalid value")
        identities = tuple(value.span_id.value for value in values)
        if len(identities) != len(set(identities)):
            raise ReadingEvidenceError("source spans must be unique")
        object.__setattr__(self, "_spans", values)

    def __bool__(self) -> bool:
        return bool(self._spans)

    def __iter__(self) -> Iterator[ReadingSourceSpanEvidence]:
        return iter(self._spans)

    def __len__(self) -> int:
        return len(self._spans)

    def identity_material(self) -> list[str]:
        """Return ephemeral canonical span identity material."""
        return [span.span_id.value for span in self._spans]
