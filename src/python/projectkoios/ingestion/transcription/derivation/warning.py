from __future__ import annotations

from dataclasses import dataclass

from projectkoios.ingestion.base.derivation import AbstractDerivation
from projectkoios.ingestion.models import IngestionWarning, WarningSeverity
from projectkoios.ingestion.transcription.base import (
    AbstractTranscriptionDataObject,
)
from projectkoios.ingestion.transcription.derivation.transcription import (
    TranscriptionDerivation,
)


@dataclass(frozen=True)
class TranscriptionWarningDerivation(
    AbstractDerivation, AbstractTranscriptionDataObject
):
    item_id: str
    code: str
    warning: IngestionWarning
    contract_version: str = AbstractTranscriptionDataObject.CONTRACT_VERSION

    @classmethod
    def derive(
        cls, draft: TranscriptionDerivation, code: str
    ) -> TranscriptionWarningDerivation:
        if code == "transcription.order_uncertain":
            message = (
                "Item ordering uses uncertain extractor source order because "
                "geometry and structure order are unavailable."
            )
        elif code == "transcription.raw_block_fallback":
            message = (
                "Raw text is included as an explicit fallback because no "
                "selected structure item represents the block."
            )
        else:
            raise ValueError("unsupported transcription warning derivation")
        warning = IngestionWarning.create(
            code=code,
            severity=WarningSeverity.WARNING,
            message=message,
            object_ids=(draft.source_object_id,),
            source_spans=draft.source_spans,
            evidence=(("item_kind", draft.item_kind.value),),
        )
        return cls(item_id=draft.item_id, code=code, warning=warning)

    def __post_init__(self) -> None:
        if self.contract_version != self.CONTRACT_VERSION:
            raise ValueError(
                "unsupported transcription warning derivation version"
            )
        self.validate_identity_fields(self.item_id, self.code)
        if not isinstance(self.warning, IngestionWarning):
            raise TypeError(
                "transcription warning derivation requires a warning"
            )
        if self.warning.code != self.code:
            raise ValueError(
                "transcription warning derivation code is inconsistent"
            )
