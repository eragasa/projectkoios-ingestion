"""Pure exact equation-block projection."""

from __future__ import annotations

from projectkoios.ingestion.transcript.reading.evidence.block.equation.evidence import (  # noqa: E501
    ReadingEquationEvidenceBlock,
)
from projectkoios.ingestion.transcript.reading.evidence.equation.disposition import (  # noqa: E501
    ReadingEquationSelectionDisposition,
)
from projectkoios.ingestion.transcript.reading.evidence.error import (
    ReadingEvidenceError,
)
from projectkoios.ingestion.transcript.reading.evidence.input.equation.inventory import (  # noqa: E501
    ReadingEquationProducerEvidenceInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.input.structure.evidence import (  # noqa: E501
    ReadingStructuredItemProducerEvidence,
)


def project_reading_equation_evidence_block(
    *,
    item: ReadingStructuredItemProducerEvidence,
    equations: ReadingEquationProducerEvidenceInventory,
    disposition: ReadingEquationSelectionDisposition,
) -> ReadingEquationEvidenceBlock:
    """Join one structured equation item to configured primary evidence."""
    producer = next(
        (
            value
            for value in equations
            if value.lineage.source_object_id == item.source_object_id
        ),
        None,
    )
    if producer is None:
        raise ReadingEvidenceError("equation item lacks producer evidence")
    if producer.selection_disposition is not disposition:
        raise ReadingEvidenceError(
            "ordered equation differs from configured disposition"
        )
    return ReadingEquationEvidenceBlock(
        structured_item=item,
        producer_evidence=producer,
    )
