"""Pure exact text-block projection."""

from __future__ import annotations

from projectkoios.ingestion.transcript.reading.evidence.block.text.basis import (  # noqa: E501
    ReadingTextBlockProjectionBasis,
)
from projectkoios.ingestion.transcript.reading.evidence.block.text.evidence import (  # noqa: E501
    ReadingTextEvidenceBlock,
)
from projectkoios.ingestion.transcript.reading.evidence.block.text.source import (  # noqa: E501
    ReadingTextBlockSourceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.error import (
    ReadingEvidenceError,
)
from projectkoios.ingestion.transcript.reading.evidence.input.structure.evidence import (  # noqa: E501
    ReadingStructuredItemProducerEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.input.text.inventory import (  # noqa: E501
    ReadingCleanTextProducerEvidenceInventory,
)


def project_reading_text_evidence_block(
    *,
    item: ReadingStructuredItemProducerEvidence,
    clean_text: ReadingCleanTextProducerEvidenceInventory,
    basis: ReadingTextBlockProjectionBasis,
) -> ReadingTextEvidenceBlock:
    """Join one structured text item to exact ordered clean-text evidence."""
    by_source_block = {value.source_block_id: value for value in clean_text}
    try:
        source_values = tuple(
            by_source_block[source_id] for source_id in item.source_block_ids
        )
    except KeyError as error:
        raise ReadingEvidenceError(
            "structured text item lacks exact clean-text evidence"
        ) from error
    return ReadingTextEvidenceBlock(
        structured_item=item,
        sources=ReadingTextBlockSourceInventory(*source_values),
        basis=basis,
    )
