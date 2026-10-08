"""Pure current structured-item producer action."""

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
from projectkoios.ingestion.transcript.reading.evidence.input.structure.evidence import (  # noqa: E501
    ReadingStructuredItemProducerEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.input.structure.inventory import (  # noqa: E501
    ReadingStructuredItemProducerEvidenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.input.structure.kind import (  # noqa: E501
    ReadingStructuredItemKind,
)
from projectkoios.ingestion.transcript.reading.evidence.input.structure.production.request import (  # noqa: E501
    ReadingStructuredItemProductionRequest,
)
from projectkoios.ingestion.transcript.reading.evidence.input.structure.production.result import (  # noqa: E501
    ReadingStructuredItemProductionResult,
)
from projectkoios.ingestion.transcription.kind.item import TranscriptionItemKind


class ReadingStructuredItemProducerActionizer(
    DataObjectActionizer[
        ReadingStructuredItemProductionRequest,
        ReadingStructuredItemProductionResult,
    ]
):
    """Project current transcription items into typed producer evidence."""

    __slots__ = ()

    def action(
        self,
        *,
        request: ReadingStructuredItemProductionRequest,
    ) -> ReadingStructuredItemProductionResult:
        """Return bounded structured-item evidence without I/O."""
        if type(request) is not ReadingStructuredItemProductionRequest:
            raise TypeError(
                "request must be ReadingStructuredItemProductionRequest"
            )
        transcription = request.transcription
        page_text = tuple(request.page_text)
        producer_id = ReadingEvidenceIdentity(
            kind=ReadingEvidenceIdentityKind.PRODUCER,
            value=transcription.processor_name,
        )
        page_orders: dict[int, int] = {}
        records: list[ReadingStructuredItemProducerEvidence] = []
        for item in transcription.items:
            if item.item_kind is TranscriptionItemKind.PAGE_ANCHOR:
                continue
            if item.item_kind is TranscriptionItemKind.PROSE:
                kind = ReadingStructuredItemKind.PARAGRAPH
            elif item.item_kind is TranscriptionItemKind.HEADING:
                kind = ReadingStructuredItemKind.HEADING
            elif item.item_kind is TranscriptionItemKind.FIGURE:
                kind = ReadingStructuredItemKind.FIGURE
            elif item.item_kind is TranscriptionItemKind.TABLE:
                kind = ReadingStructuredItemKind.TABLE
            elif item.item_kind is TranscriptionItemKind.EQUATION:
                kind = ReadingStructuredItemKind.EQUATION
            else:
                raise TypeError("transcription item kind is unsupported")

            order_index = page_orders.get(item.page_index, 0)
            page_orders[item.page_index] = order_index + 1
            is_text = kind in (
                ReadingStructuredItemKind.PARAGRAPH,
                ReadingStructuredItemKind.HEADING,
            )
            source_blocks = tuple(
                sorted(
                    (
                        ReadingEvidenceIdentity(
                            kind=ReadingEvidenceIdentityKind.SOURCE_BLOCK,
                            value=value,
                        )
                        for value in item.source_block_ids
                    ),
                    key=lambda value: value.value,
                )
            )
            records.append(
                ReadingStructuredItemProducerEvidence(
                    page_location=page_text[
                        item.page_index
                    ].streams.page_location,
                    order_index=order_index,
                    kind=kind,
                    source_block_ids=ReadingEvidenceIdentityInventory(
                        ReadingEvidenceIdentityKind.SOURCE_BLOCK,
                        *(source_blocks if is_text else ()),
                    ),
                    source_object_id=(
                        None
                        if is_text
                        else ReadingEvidenceIdentity(
                            kind=ReadingEvidenceIdentityKind.SOURCE_OBJECT,
                            value=item.source_object_id,
                        )
                    ),
                    producer_id=producer_id,
                    producer_version=transcription.processor_version,
                )
            )

        page_ids = tuple(
            sorted(
                (value.record_id for value in page_text),
                key=lambda value: value.value,
            )
        )
        return ReadingStructuredItemProductionResult(
            source_result_id=ReadingEvidenceIdentity(
                kind=ReadingEvidenceIdentityKind.STRUCTURED_TRANSCRIPTION,
                value=transcription.result_id,
            ),
            page_text_ids=ReadingEvidenceIdentityInventory(
                ReadingEvidenceIdentityKind.PAGE_TEXT,
                *page_ids,
            ),
            evidence=ReadingStructuredItemProducerEvidenceInventory(*records),
        )
