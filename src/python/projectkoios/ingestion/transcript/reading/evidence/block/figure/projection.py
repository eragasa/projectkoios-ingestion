"""Pure exact figure-block projection."""

from __future__ import annotations

from projectkoios.ingestion.transcript.reading.evidence.block.figure.evidence import (  # noqa: E501
    ReadingFigureEvidenceBlock,
)
from projectkoios.ingestion.transcript.reading.evidence.caption.basis import (
    ReadingCaptionSelectionBasis,
)
from projectkoios.ingestion.transcript.reading.evidence.caption.selection import (  # noqa: E501
    derive_reading_caption_evidence,
)
from projectkoios.ingestion.transcript.reading.evidence.error import (
    ReadingEvidenceError,
)
from projectkoios.ingestion.transcript.reading.evidence.input.figure.inventory import (  # noqa: E501
    ReadingFigureProducerEvidenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.input.structure.evidence import (  # noqa: E501
    ReadingStructuredItemProducerEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.projection.configuration import (  # noqa: E501
    ReadingEvidenceProjectionConfiguration,
)


def project_reading_figure_evidence_block(
    *,
    item: ReadingStructuredItemProducerEvidence,
    figures: ReadingFigureProducerEvidenceInventory,
    configuration: ReadingEvidenceProjectionConfiguration,
    caption_basis: ReadingCaptionSelectionBasis,
) -> ReadingFigureEvidenceBlock:
    """Join one structured figure item to one exact admissible producer."""
    producer = next(
        (
            value
            for value in figures
            if value.lineage.source_object_id == item.source_object_id
        ),
        None,
    )
    if producer is None:
        raise ReadingEvidenceError("figure item lacks producer evidence")
    if not configuration.admits_visual_status(
        producer.assessment.visual_status
    ):
        raise ReadingEvidenceError("figure producer status is inadmissible")
    return ReadingFigureEvidenceBlock(
        structured_item=item,
        producer_evidence=producer,
        caption=derive_reading_caption_evidence(
            producer=producer,
            basis=caption_basis,
        ),
    )
