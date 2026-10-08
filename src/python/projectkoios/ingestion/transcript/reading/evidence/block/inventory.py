"""Ordered heterogeneous canonical reading block inventories."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from projectkoios.ingestion.transcript.reading.evidence.block.equation.evidence import (  # noqa: E501
    ReadingEquationEvidenceBlock,
)
from projectkoios.ingestion.transcript.reading.evidence.block.figure.evidence import (  # noqa: E501
    ReadingFigureEvidenceBlock,
)
from projectkoios.ingestion.transcript.reading.evidence.block.table.evidence import (  # noqa: E501
    ReadingTableEvidenceBlock,
)
from projectkoios.ingestion.transcript.reading.evidence.block.text.evidence import (  # noqa: E501
    ReadingTextEvidenceBlock,
)
from projectkoios.ingestion.transcript.reading.evidence.error import (
    ReadingEvidenceError,
)
from projectkoios.ingestion.transcript.reading.evidence.limits.definition import (  # noqa: E501
    READING_EVIDENCE_LIMITS,
)
from projectkoios.ingestion.transcript.reading.evidence.limits.error import (
    ReadingEvidenceLimitError,
)

ReadingEvidenceBlock = (
    ReadingTextEvidenceBlock
    | ReadingFigureEvidenceBlock
    | ReadingTableEvidenceBlock
    | ReadingEquationEvidenceBlock
)
_BLOCK_TYPES = (
    ReadingTextEvidenceBlock,
    ReadingFigureEvidenceBlock,
    ReadingTableEvidenceBlock,
    ReadingEquationEvidenceBlock,
)


@dataclass(frozen=True, slots=True, init=False)
class ReadingEvidenceBlockInventory:
    """Own one page's unique contiguous heterogeneous reading order."""

    _blocks: tuple[ReadingEvidenceBlock, ...] = field(repr=True)

    def __init__(self, *blocks: ReadingEvidenceBlock) -> None:
        values = tuple(blocks)
        if len(values) > READING_EVIDENCE_LIMITS.maximum_blocks:
            raise ReadingEvidenceLimitError("block count exceeds its limit")
        if any(type(value) not in _BLOCK_TYPES for value in values):
            raise TypeError("block inventory contains an invalid value")
        identities = tuple(value.block_id.value for value in values)
        if len(identities) != len(set(identities)):
            raise ReadingEvidenceError("reading blocks must be unique")
        orders = tuple(value.order_index for value in values)
        if orders != tuple(range(len(values))):
            raise ReadingEvidenceError("reading block order must be contiguous")
        if values and any(
            value.page_location != values[0].page_location for value in values
        ):
            raise ReadingEvidenceError("reading blocks must bind one page")
        text_bytes = sum(
            len(value.text.encode())
            for value in values
            if type(value) is ReadingTextEvidenceBlock
        )
        if text_bytes > READING_EVIDENCE_LIMITS.maximum_page_text_bytes:
            raise ReadingEvidenceLimitError("page block text exceeds its limit")
        object.__setattr__(self, "_blocks", values)

    def __bool__(self) -> bool:
        return bool(self._blocks)

    def __iter__(self) -> Iterator[ReadingEvidenceBlock]:
        return iter(self._blocks)

    def __len__(self) -> int:
        return len(self._blocks)

    def identity_material(self) -> list[str]:
        """Return ephemeral canonical block identity material."""
        return [value.block_id.value for value in self._blocks]
