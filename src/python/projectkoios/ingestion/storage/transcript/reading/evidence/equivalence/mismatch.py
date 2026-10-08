"""Typed reading-evidence source equivalence differences."""

from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import StrEnum


class ReadingEvidenceEquivalenceMismatch(StrEnum):
    """Classify exact canonical and replay-evidence differences."""

    DOCUMENT = "document"
    INVENTORY = "inventory"
    PROJECTION_RESULT = "projection_result"
    REPLAY_OUTCOME = "replay_outcome"


@dataclass(frozen=True, slots=True, init=False)
class ReadingEvidenceEquivalenceMismatchInventory:
    """Own a canonical unique set of equivalence differences."""

    _values: tuple[ReadingEvidenceEquivalenceMismatch, ...] = field(repr=True)

    def __init__(self, *values: ReadingEvidenceEquivalenceMismatch) -> None:
        items = tuple(values)
        if any(
            not isinstance(value, ReadingEvidenceEquivalenceMismatch)
            for value in items
        ):
            raise TypeError("equivalence mismatch inventory is invalid")
        expected = tuple(sorted(set(items), key=lambda value: value.value))
        if items != expected:
            raise ValueError("equivalence mismatches must be canonical")
        object.__setattr__(self, "_values", items)

    def __iter__(self) -> Iterator[ReadingEvidenceEquivalenceMismatch]:
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)
