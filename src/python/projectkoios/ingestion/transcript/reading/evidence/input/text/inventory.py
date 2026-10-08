"""Page/source-ordered clean-text producer inventories."""

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
class ReadingCleanTextProducerEvidenceInventory:
    """Own canonical page/source-ordered clean-text producer evidence."""

    _records: tuple[ReadingCleanTextProducerEvidence, ...] = field(repr=True)

    def __init__(self, *records: ReadingCleanTextProducerEvidence) -> None:
        values = tuple(records)
        if len(values) > READING_EVIDENCE_LIMITS.maximum_blocks:
            raise ReadingEvidenceLimitError(
                "clean-text record count exceeds its limit"
            )
        if any(
            type(value) is not ReadingCleanTextProducerEvidence
            for value in values
        ):
            raise TypeError("clean-text inventory contains an invalid value")
        order = tuple(
            (value.page_location.physical_page_index, value.order_index)
            for value in values
        )
        if order != tuple(sorted(order)) or len(order) != len(set(order)):
            raise ReadingEvidenceError(
                "clean-text records require unique page/source order"
            )
        page_orders: dict[int, list[int]] = {}
        for page_index, order_index in order:
            page_orders.setdefault(page_index, []).append(order_index)
        if any(
            indexes != list(range(len(indexes)))
            for indexes in page_orders.values()
        ):
            raise ReadingEvidenceError(
                "clean-text order must be contiguous per page"
            )
        block_ids = tuple(value.source_block_id.value for value in values)
        record_ids = tuple(value.record_id.value for value in values)
        if len(block_ids) != len(set(block_ids)) or len(record_ids) != len(
            set(record_ids)
        ):
            raise ReadingEvidenceError("clean-text identities must be unique")
        character_count = sum(
            len(value.raw_text) + len(value.clean_text) for value in values
        )
        if (
            character_count
            > READING_EVIDENCE_LIMITS.maximum_aggregate_characters
        ):
            raise ReadingEvidenceLimitError(
                "clean-text evidence exceeds its aggregate character limit"
            )
        byte_count = sum(
            len(value.raw_text.encode()) + len(value.clean_text.encode())
            for value in values
        )
        if (
            byte_count
            > READING_EVIDENCE_LIMITS.maximum_document_clean_text_bytes
        ):
            raise ReadingEvidenceLimitError(
                "clean-text evidence exceeds its aggregate byte limit"
            )
        if (
            sum(len(value.transformations) for value in values)
            > READING_EVIDENCE_LIMITS.maximum_total_transformations
        ):
            raise ReadingEvidenceLimitError(
                "clean-text transformations exceed their aggregate limit"
            )
        object.__setattr__(self, "_records", values)

    def __bool__(self) -> bool:
        return bool(self._records)

    def __iter__(self) -> Iterator[ReadingCleanTextProducerEvidence]:
        return iter(self._records)

    def __len__(self) -> int:
        return len(self._records)

    def identity_material(self) -> list[str]:
        """Return ephemeral canonical clean-text identity material."""
        return [value.record_id.value for value in self._records]
