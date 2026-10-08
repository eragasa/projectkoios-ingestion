"""Declared-order clean-text sources for one canonical text block."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from projectkoios.ingestion.transcript.reading.evidence.error import (
    ReadingEvidenceError,
)
from projectkoios.ingestion.transcript.reading.evidence.input.text.evidence import (  # noqa: E501
    ReadingCleanTextProducerEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.limits.definition import (  # noqa: E501
    READING_EVIDENCE_LIMITS,
)
from projectkoios.ingestion.transcript.reading.evidence.limits.error import (
    ReadingEvidenceLimitError,
)


@dataclass(frozen=True, slots=True, init=False)
class ReadingTextBlockSourceInventory:
    """Own one unique bounded clean-text sequence in source-block order."""

    _records: tuple[ReadingCleanTextProducerEvidence, ...] = field(repr=True)

    def __init__(self, *records: ReadingCleanTextProducerEvidence) -> None:
        values = tuple(records)
        if not values:
            raise ReadingEvidenceError("text block requires clean-text sources")
        if len(values) > READING_EVIDENCE_LIMITS.maximum_identities:
            raise ReadingEvidenceLimitError(
                "text-block source count exceeds its limit"
            )
        if any(
            type(value) is not ReadingCleanTextProducerEvidence
            for value in values
        ):
            raise TypeError(
                "text-block source inventory contains an invalid value"
            )
        record_ids = tuple(value.record_id.value for value in values)
        block_ids = tuple(value.source_block_id.value for value in values)
        if len(record_ids) != len(set(record_ids)) or len(block_ids) != len(
            set(block_ids)
        ):
            raise ReadingEvidenceError("text-block sources must be unique")
        first = values[0]
        if any(
            value.page_location != first.page_location
            or value.selected_stream_id != first.selected_stream_id
            for value in values
        ):
            raise ReadingEvidenceError(
                "text-block sources must bind one page and selected stream"
            )
        source_orders = tuple(value.order_index for value in values)
        if source_orders != tuple(
            range(source_orders[0], source_orders[0] + len(source_orders))
        ):
            raise ReadingEvidenceError(
                "text-block sources must be contiguous and ordered"
            )
        object.__setattr__(self, "_records", values)

    def __iter__(self) -> Iterator[ReadingCleanTextProducerEvidence]:
        return iter(self._records)

    def __len__(self) -> int:
        return len(self._records)

    def identity_material(self) -> list[str]:
        """Return ephemeral canonical clean-text source material."""
        return [value.record_id.value for value in self._records]
