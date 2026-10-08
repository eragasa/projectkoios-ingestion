"""Pure exact caption selection for canonical figure evidence."""

from __future__ import annotations

from projectkoios.ingestion.transcript.reading.evidence.association.role import (  # noqa: E501
    ReadingAssociationRole,
)
from projectkoios.ingestion.transcript.reading.evidence.caption.basis import (
    ReadingCaptionSelectionBasis,
)
from projectkoios.ingestion.transcript.reading.evidence.caption.evidence import (  # noqa: E501
    ReadingCaptionEvidence,
)
from projectkoios.ingestion.transcript.reading.evidence.error import (
    ReadingEvidenceError,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.inventory import (  # noqa: E501
    ReadingEvidenceIdentityInventory,
)
from projectkoios.ingestion.transcript.reading.evidence.identity.kind import (
    ReadingEvidenceIdentityKind,
)
from projectkoios.ingestion.transcript.reading.evidence.input.figure.evidence import (  # noqa: E501
    ReadingFigureProducerEvidence,
)


def derive_reading_caption_evidence(
    *,
    producer: ReadingFigureProducerEvidence,
    basis: ReadingCaptionSelectionBasis,
) -> ReadingCaptionEvidence | None:
    """Select one normalized unique caption from exact typed associations."""
    if type(producer) is not ReadingFigureProducerEvidence:
        raise TypeError("producer must be ReadingFigureProducerEvidence")
    if not isinstance(basis, ReadingCaptionSelectionBasis):
        raise TypeError("basis must be ReadingCaptionSelectionBasis")
    caption_associations = tuple(
        value
        for value in producer.assessment.associations
        if value.role is ReadingAssociationRole.CAPTION
    )
    if not caption_associations:
        return None
    normalized = tuple(
        " ".join(value.text.split()) for value in caption_associations
    )
    if len({value.casefold() for value in normalized}) != 1:
        raise ReadingEvidenceError("figure has conflicting normalized captions")
    association_ids = tuple(
        sorted(
            (value.association_id for value in caption_associations),
            key=lambda value: value.value,
        )
    )
    return ReadingCaptionEvidence(
        text=min(normalized),
        association_ids=ReadingEvidenceIdentityInventory(
            ReadingEvidenceIdentityKind.ASSOCIATION,
            *association_ids,
        ),
        basis=basis,
    )
