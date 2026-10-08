"""Pure exact table-block projection."""

from __future__ import annotations

from projectkoios.ingestion.transcript.reading.evidence.block.table.evidence import (  # noqa: E501
    ReadingTableEvidenceBlock,
)
from projectkoios.ingestion.transcript.reading.evidence.error import (
    ReadingEvidenceError,
)
from projectkoios.ingestion.transcript.reading.evidence.input.structure.evidence import (  # noqa: E501
    ReadingStructuredItemProducerEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.input.table.inventory import (  # noqa: E501
    ReadingTableProducerEvidenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.projection.configuration import (  # noqa: E501
    ReadingEvidenceProjectionConfiguration,
)


def project_reading_table_evidence_block(
    *,
    item: ReadingStructuredItemProducerEvidence,
    tables: ReadingTableProducerEvidenceInventory,
    configuration: ReadingEvidenceProjectionConfiguration,
) -> ReadingTableEvidenceBlock:
    """Join one structured table item to one exact admissible producer."""
    producer = next(
        (
            value
            for value in tables
            if value.lineage.source_object_id == item.source_object_id
        ),
        None,
    )
    if producer is None:
        raise ReadingEvidenceError("table item lacks producer evidence")
    if not configuration.admits_visual_status(
        producer.assessment.visual_status
    ):
        raise ReadingEvidenceError("table producer status is inadmissible")
    return ReadingTableEvidenceBlock(
        structured_item=item,
        producer_evidence=producer,
    )
