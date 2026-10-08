"""Mismatch-field inventories for reading evidence reconciliation."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from projectkoios.ingestion.transcript.reading.evidence.error import (
    ReadingEvidenceError,
)
from projectkoios.ingestion.transcript.reading.evidence.reconciliation.field import (  # noqa: E501
    ReadingEvidenceInventoryField,
)


@dataclass(frozen=True, slots=True, init=False)
class ReadingEvidenceReconciliationMismatchInventory:
    """Own one sorted unique collection of conflicting inventory fields."""

    _fields: tuple[ReadingEvidenceInventoryField, ...] = field(repr=True)

    def __init__(self, *fields: ReadingEvidenceInventoryField) -> None:
        values = tuple(fields)
        if any(
            not isinstance(value, ReadingEvidenceInventoryField)
            for value in values
        ):
            raise TypeError("reconciliation mismatch field is invalid")
        if values != tuple(
            sorted(values, key=lambda value: value.value)
        ) or len(values) != len(set(values)):
            raise ReadingEvidenceError(
                "mismatch fields must be sorted and unique"
            )
        object.__setattr__(self, "_fields", values)

    def __bool__(self) -> bool:
        return bool(self._fields)

    def __iter__(self) -> Iterator[ReadingEvidenceInventoryField]:
        return iter(self._fields)

    def __len__(self) -> int:
        return len(self._fields)

    def identity_material(self) -> list[str]:
        """Return ephemeral canonical mismatch field material."""
        return [value.value for value in self._fields]
