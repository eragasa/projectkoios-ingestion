"""Semantic source-label inventories for reading evidence."""

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


@dataclass(frozen=True, slots=True, init=False)
class ReadingSourceLabelInventory:
    """Own one source-ordered, unique, bounded label collection."""

    _labels: tuple[str, ...] = field(repr=True)

    def __init__(self, *labels: str) -> None:
        values = tuple(labels)
        if len(values) > READING_EVIDENCE_LIMITS.maximum_labels:
            raise ReadingEvidenceLimitError(
                "source label count exceeds its limit"
            )
        for index, value in enumerate(values):
            READING_EVIDENCE_LIMITS.require_text(
                value,
                f"source_labels[{index}]",
                maximum_bytes=READING_EVIDENCE_LIMITS.maximum_label_bytes,
            )
        if len(values) != len(set(values)):
            raise ReadingEvidenceError("source labels must be unique")
        object.__setattr__(self, "_labels", values)

    def __bool__(self) -> bool:
        return bool(self._labels)

    def __iter__(self) -> Iterator[str]:
        return iter(self._labels)

    def __len__(self) -> int:
        return len(self._labels)

    def identity_material(self) -> list[str]:
        """Return ephemeral canonical label material."""
        return list(self._labels)
