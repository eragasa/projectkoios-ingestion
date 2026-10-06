from __future__ import annotations

from enum import StrEnum

from projectkoios.ingestion.models import IngestionWarning
from projectkoios.ingestion.transcription.item import TranscriptionItem
from projectkoios.ingestion.transcription.omission import (
    TranscriptionOmission,
)
from projectkoios.ingestion.transcription.status.evidence import (
    TranscriptionEvidenceStatus,
)
from projectkoios.ingestion.transcription.status.order import (
    TranscriptionOrderStatus,
)


class TranscriptionStatus(StrEnum):
    PROPOSED = "proposed"
    PROPOSED_WITH_UNCERTAINTY = "proposed_with_uncertainty"

    @classmethod
    def determine(
        cls,
        items: tuple[TranscriptionItem, ...],
        omissions: tuple[TranscriptionOmission, ...],
        warnings: tuple[IngestionWarning, ...],
    ) -> TranscriptionStatus:
        if (
            omissions
            or warnings
            or any(
                item.evidence_status is TranscriptionEvidenceStatus.AMBIGUOUS
                or item.order_status
                is TranscriptionOrderStatus.UNCERTAIN_SOURCE_ORDER
                for item in items
            )
        ):
            return cls.PROPOSED_WITH_UNCERTAINTY
        return cls.PROPOSED
