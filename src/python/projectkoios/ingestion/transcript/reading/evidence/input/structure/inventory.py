"""Complete ordered structured-item producer inventories."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from projectkoios.ingestion.transcript.reading.evidence.error import (
    ReadingEvidenceError,
)
from projectkoios.ingestion.transcript.reading.evidence.input.structure.evidence import (  # noqa: E501
    ReadingStructuredItemProducerEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.limits.definition import (  # noqa: E501
    READING_EVIDENCE_LIMITS,
)
from projectkoios.ingestion.transcript.reading.evidence.limits.error import (
    ReadingEvidenceLimitError,
)


@dataclass(frozen=True, slots=True, init=False)
class ReadingStructuredItemProducerEvidenceInventory:
    """Own complete contiguous page-ordered structured producer items."""

    _items: tuple[ReadingStructuredItemProducerEvidence, ...] = field(repr=True)

    def __init__(self, *items: ReadingStructuredItemProducerEvidence) -> None:
        values = tuple(items)
        if len(values) > READING_EVIDENCE_LIMITS.maximum_blocks:
            raise ReadingEvidenceLimitError(
                "structured-item count exceeds its limit"
            )
        if any(
            type(value) is not ReadingStructuredItemProducerEvidence
            for value in values
        ):
            raise TypeError(
                "structured-item inventory contains an invalid value"
            )
        order = tuple(
            (value.page_location.physical_page_index, value.order_index)
            for value in values
        )
        if order != tuple(sorted(order)) or len(order) != len(set(order)):
            raise ReadingEvidenceError(
                "structured items require unique page order"
            )
        page_orders: dict[int, list[int]] = {}
        for page_index, order_index in order:
            page_orders.setdefault(page_index, []).append(order_index)
        if any(
            indexes != list(range(len(indexes)))
            for indexes in page_orders.values()
        ):
            raise ReadingEvidenceError(
                "structured item order must be contiguous per page"
            )
        identities = tuple(value.record_id.value for value in values)
        if len(identities) != len(set(identities)):
            raise ReadingEvidenceError(
                "structured item identities must be unique"
            )
        object.__setattr__(self, "_items", values)

    def __bool__(self) -> bool:
        return bool(self._items)

    def __iter__(self) -> Iterator[ReadingStructuredItemProducerEvidence]:
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def identity_material(self) -> list[str]:
        """Return ephemeral canonical structured-item identity material."""
        return [value.record_id.value for value in self._items]
