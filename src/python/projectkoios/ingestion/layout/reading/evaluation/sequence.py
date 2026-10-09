"""Bounded normalized element sequences for reading-order evaluation."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from projectkoios.ingestion.identity import stable_id
from projectkoios.ingestion.layout.limits.definition import (
    MAX_LAYOUT_IDENTITY_FIELD_CHARACTERS,
)
from projectkoios.ingestion.layout.reading.order.limits import (
    MAX_LAYOUT_READING_ORDER_ELEMENTS,
)


@dataclass(frozen=True, slots=True, init=False)
class LayoutReadingOrderNormalizedElementSequence:
    """Retain a normalized sequence, including malformed values."""

    _element_ids: tuple[str, ...] = field(repr=True)
    sequence_id: str = field(init=False)

    def __init__(self, *element_ids: str) -> None:
        if len(element_ids) > MAX_LAYOUT_READING_ORDER_ELEMENTS:
            raise ValueError(
                "normalized element sequence exceeds implementation limit"
            )
        values: list[str] = []
        for element_id in element_ids:
            if not isinstance(element_id, str):
                raise TypeError("normalized element IDs must be strings")
            if len(element_id) > MAX_LAYOUT_IDENTITY_FIELD_CHARACTERS:
                raise ValueError(
                    "normalized element ID exceeds implementation limit"
                )
            values.append(element_id)
        sequence = tuple(values)
        object.__setattr__(self, "_element_ids", sequence)
        object.__setattr__(
            self,
            "sequence_id",
            stable_id(
                "layout-reading-order-normalized-element-sequence", sequence
            ),
        )

    def __iter__(self) -> Iterator[str]:
        return iter(self._element_ids)

    def __len__(self) -> int:
        return len(self._element_ids)
