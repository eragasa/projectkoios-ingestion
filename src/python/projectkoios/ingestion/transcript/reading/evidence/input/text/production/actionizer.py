"""Pure current clean-text producer action."""

from __future__ import annotations

from projectkoios.base import DataObjectActionizer
from projectkoios.ingestion.transcript.reading.evidence.identity.definition import (  # noqa: E501
    ReadingEvidenceIdentity,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.inventory import (  # noqa: E501
    ReadingEvidenceIdentityInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.kind import (
    ReadingEvidenceIdentityKind,
)
from projectkoios.ingestion.transcript.reading.evidence.input.text.evidence import (  # noqa: E501
    ReadingCleanTextProducerEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.input.text.inventory import (  # noqa: E501
    ReadingCleanTextProducerEvidenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.input.text.production.request import (  # noqa: E501
    ReadingCleanTextProductionRequest,
)
from projectkoios.ingestion.transcript.reading.evidence.input.text.production.result import (  # noqa: E501
    ReadingCleanTextProductionResult,
)
from projectkoios.ingestion.transcript.reading.evidence.input.text.production.transformation import (  # noqa: E501
    derive_reading_clean_text_transformations,
)


class ReadingCleanTextProducerActionizer(
    DataObjectActionizer[
        ReadingCleanTextProductionRequest,
        ReadingCleanTextProductionResult,
    ]
):
    """Project current clean blocks into exact typed producer evidence."""

    __slots__ = ()

    def action(
        self,
        *,
        request: ReadingCleanTextProductionRequest,
    ) -> ReadingCleanTextProductionResult:
        """Return bounded replayable clean-text evidence without I/O."""
        if type(request) is not ReadingCleanTextProductionRequest:
            raise TypeError("request must be ReadingCleanTextProductionRequest")
        transcript = request.transcript
        page_text = tuple(request.page_text)
        producer_id = ReadingEvidenceIdentity(
            kind=ReadingEvidenceIdentityKind.PRODUCER,
            value=transcript.processor_name,
        )
        page_orders: dict[int, int] = {}
        records: list[ReadingCleanTextProducerEvidence] = []
        for block in transcript.blocks:
            order_index = page_orders.get(block.page_index, 0)
            page_orders[block.page_index] = order_index + 1
            page = page_text[block.page_index]
            records.append(
                ReadingCleanTextProducerEvidence(
                    selected_stream_id=page.selection.selected_stream_id,
                    source_block_id=ReadingEvidenceIdentity(
                        kind=ReadingEvidenceIdentityKind.SOURCE_BLOCK,
                        value=block.block_id,
                    ),
                    page_location=page.streams.page_location,
                    order_index=order_index,
                    raw_text=block.raw_text,
                    clean_text=block.clean_text,
                    transformations=derive_reading_clean_text_transformations(
                        block=block,
                        transcript=transcript,
                    ),
                    producer_id=producer_id,
                    producer_version=transcript.processor_version,
                )
            )

        page_ids = tuple(
            sorted(
                (value.record_id for value in page_text),
                key=lambda value: value.value,
            )
        )
        return ReadingCleanTextProductionResult(
            source_result_id=ReadingEvidenceIdentity(
                kind=ReadingEvidenceIdentityKind.CLEAN_TRANSCRIPT,
                value=transcript.result_id,
            ),
            page_text_ids=ReadingEvidenceIdentityInventory(
                ReadingEvidenceIdentityKind.PAGE_TEXT,
                *page_ids,
            ),
            evidence=ReadingCleanTextProducerEvidenceInventory(*records),
        )
